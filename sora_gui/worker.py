"""Background worker for API interactions"""
import os
import time
import random
import mimetypes
import logging
from pathlib import Path
from collections import deque
from typing import Optional, Dict, Any, Tuple

import requests
from PySide6.QtCore import QObject, Signal

from .constants import (
    API_BASE, DOWNLOAD_CHUNK_SIZE, TIMEOUT_POST, TIMEOUT_GET, 
    TIMEOUT_DOWNLOAD, MAX_BACKOFF, BACKOFF_MULTIPLIER, STUCK_CHECK_INTERVAL
)
from .utils import safe_json, pretty

logger = logging.getLogger(__name__)

class Worker(QObject):
    progressed = Signal(int)
    logged = Signal(str)
    finished = Signal()
    failed = Signal(str)
    saved = Signal(str)
    lastresp = Signal(dict)
    jobid = Signal(str)

    def __init__(self, api_key: str, model: str, size: str, seconds: str, prompt: str, 
                 ref_path: str, out_dir: str, job_id: Optional[str], 
                 poll_every: int, max_minutes: int):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.size = size
        self.seconds = seconds
        self.prompt = prompt
        self.ref_path = ref_path
        self.out_dir = Path(out_dir)
        self.job_id = job_id
        self.poll_every = poll_every
        self.max_minutes = max_minutes
        self.req_ids = deque(maxlen=10)
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the worker operation"""
        self._cancelled = True
        logger.info("Worker cancellation requested")

    def record(self, resp: requests.Response, endpoint: str) -> Dict[str, Any]:
        """Record API response and emit signal"""
        rid = resp.headers.get("x-request-id") or resp.headers.get("X-Request-Id")
        body = safe_json(resp)
        payload = {"endpoint": endpoint, "status": resp.status_code, "body": body}
        if rid:
            payload["request_id"] = rid
            self.req_ids.append(rid)
        self.lastresp.emit(payload)
        return body
    
    def _download_video(self, headers: Dict[str, str], body: Dict[str, Any]) -> Optional[Path]:
        """Download video content and return path, or None on failure"""
        fn = f"{self.job_id}_{body.get('model', self.model)}_{body.get('size', self.size)}_{body.get('seconds', self.seconds)}s.mp4"
        out_path = self.out_dir / fn
        temp_path = out_path.with_suffix('.tmp')
        
        try:
            self.logged.emit("Downloading video...")
            dr = requests.get(
                f"{API_BASE}/videos/{self.job_id}/content", 
                headers=headers, 
                timeout=TIMEOUT_DOWNLOAD, 
                stream=True
            )
            dbody = {"streamed": dr.status_code == 200}
            self.lastresp.emit({
                "endpoint": f"GET /videos/{self.job_id}/content", 
                "status": dr.status_code, 
                "body": dbody
            })
            
            if dr.status_code != 200:
                self.failed.emit(f"Download error {dr.status_code}")
                return None
            
            with open(temp_path, "wb") as f:
                for chunk in dr.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if self._cancelled:
                        logger.info("Download cancelled")
                        return None
                    if chunk:
                        f.write(chunk)
            
            temp_path.rename(out_path)
            return out_path
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")
            self.failed.emit(f"Download error: {str(e)}")
            return None

    def run(self) -> None:
        """Main worker loop"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            if not self.job_id:
                self.job_id = self._submit_job(headers)
                if not self.job_id or self._cancelled:
                    return
            
            self._poll_until_complete(headers)
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            self.failed.emit("Network timeout. Check your connection and try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            self.failed.emit(f"Network error: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error in worker")
            self.failed.emit(f"Unexpected error: {str(e)}")
    
    def _submit_job(self, headers: Dict[str, str]) -> Optional[str]:
        """Submit new job to API and return job ID"""
        try:
            if self.ref_path:
                mime, _ = mimetypes.guess_type(self.ref_path)
                with open(self.ref_path, "rb") as f:
                    files = {
                        "input_reference": (
                            os.path.basename(self.ref_path), 
                            f, 
                            mime or "application/octet-stream"
                        )
                    }
                    data = {
                        "model": self.model, 
                        "prompt": self.prompt, 
                        "seconds": self.seconds, 
                        "size": self.size
                    }
                    self.logged.emit("Submitting job (multipart)...")
                    r = requests.post(
                        f"{API_BASE}/videos", 
                        headers=headers, 
                        files=files, 
                        data=data, 
                        timeout=TIMEOUT_POST
                    )
                    body = self.record(r, "POST /videos")
            else:
                payload = {
                    "model": self.model, 
                    "prompt": self.prompt, 
                    "seconds": self.seconds, 
                    "size": self.size
                }
                self.logged.emit("Submitting job (json)...")
                r = requests.post(
                    f"{API_BASE}/videos", 
                    headers={**headers, "Content-Type": "application/json"}, 
                    json=payload, 
                    timeout=TIMEOUT_POST
                )
                body = self.record(r, "POST /videos")
            
            if r.status_code not in (200, 201):
                error_msg = self._parse_error(r.status_code, body)
                self.failed.emit(error_msg)
                return None
            
            job_id = body.get("id")
            if not job_id:
                self.failed.emit(f"No job ID in response:\n{pretty(body)}")
                return None
            
            self.jobid.emit(job_id)
            status = body.get("status", "queued")
            prog = body.get("progress", 0) or 0
            self.logged.emit(f"Job id: {job_id} [{status}]")
            self.progressed.emit(int(prog))
            return job_id
        except Exception as e:
            logger.exception("Job submission failed")
            raise
    
    def _poll_until_complete(self, headers: Dict[str, str]) -> None:
        """Poll job status until completion or timeout"""
        start = time.time()
        backoff = max(1, self.poll_every)
        last_status = None
        last_prog = -1
        stuck_99 = 0
        
        while not self._cancelled:
            if time.time() - start > self.max_minutes * 60:
                ids = ", ".join(self.req_ids) if self.req_ids else "none"
                self.failed.emit(f"Timed out after {self.max_minutes} minutes. Last request IDs: {ids}")
                return
            
            try:
                pr = requests.get(
                    f"{API_BASE}/videos/{self.job_id}", 
                    headers=headers, 
                    timeout=TIMEOUT_GET
                )
            except requests.exceptions.RequestException as e:
                logger.warning(f"Poll request failed: {e}")
                self.logged.emit(f"Polling error: {str(e)}")
                time.sleep(backoff)
                backoff = min(MAX_BACKOFF, backoff + 1)
                continue
            
            body = self.record(pr, f"GET /videos/{self.job_id}")
            
            if pr.status_code >= 500:
                self.logged.emit(f"Server error {pr.status_code}, retrying...")
                logger.warning(f"Server error {pr.status_code}: {pretty(body)}")
                time.sleep(backoff + random.uniform(0, 0.5))
                backoff = min(MAX_BACKOFF, backoff * BACKOFF_MULTIPLIER)
                continue
            
            if pr.status_code != 200:
                error_msg = self._parse_error(pr.status_code, body)
                self.failed.emit(error_msg)
                return
            
            status = body.get("status", "")
            prog = int(body.get("progress", 0) or 0)
            
            if status != last_status or prog != last_prog:
                self.logged.emit(f"Status: {status} {prog}%")
                self.progressed.emit(prog)
                last_status, last_prog = status, prog
            
            if status == "completed":
                out_path = self._download_video(headers, body)
                if out_path:
                    self.saved.emit(str(out_path))
                    self.finished.emit()
                return
            
            # Workaround: Sometimes API gets stuck at 99% but video is actually ready
            # This attempts to download the video periodically when stuck
            if prog >= 99:
                stuck_99 += 1
                if stuck_99 % STUCK_CHECK_INTERVAL == 0:
                    logger.info(f"Stuck at 99%, attempting download (attempt {stuck_99 // STUCK_CHECK_INTERVAL})")
                    out_path = self._download_video(headers, body)
                    if out_path:
                        self.saved.emit(str(out_path))
                        self.finished.emit()
                        return
            else:
                stuck_99 = 0
            
            time.sleep(max(1, self.poll_every))
    
    def _parse_error(self, status_code: int, body: Dict[str, Any]) -> str:
        """Parse API error response into user-friendly message"""
        if status_code == 401:
            return "Invalid API key. Please check your key and try again."
        elif status_code == 429:
            return "Rate limit exceeded. Please wait a moment and try again."
        elif status_code == 400:
            error_msg = body.get("error", {}).get("message", "Bad request")
            return f"Request error: {error_msg}"
        else:
            return f"Error {status_code}:\n{pretty(body)}"
