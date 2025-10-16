"""Background worker for API interactions"""
import os
import time
import random
import mimetypes
from pathlib import Path
from collections import deque

import requests
from PySide6.QtCore import QObject, Signal

from .constants import API_BASE
from .utils import safe_json, pretty

class Worker(QObject):
    progressed = Signal(int)
    logged = Signal(str)
    finished = Signal()
    failed = Signal(str)
    saved = Signal(str)
    lastresp = Signal(dict)
    jobid = Signal(str)

    def __init__(self, api_key, model, size, seconds, prompt, ref_path, out_dir, job_id, poll_every, max_minutes):
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

    def record(self, resp, endpoint):
        rid = resp.headers.get("x-request-id") or resp.headers.get("X-Request-Id")
        body = safe_json(resp)
        payload = {"endpoint": endpoint, "status": resp.status_code, "body": body}
        if rid:
            payload["request_id"] = rid
            self.req_ids.append(rid)
        self.lastresp.emit(payload)
        return body

    def run(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            if not self.job_id:
                if self.ref_path:
                    mime, _ = mimetypes.guess_type(self.ref_path)
                    with open(self.ref_path, "rb") as f:
                        files = {"input_reference": (os.path.basename(self.ref_path), f, mime or "application/octet-stream")}
                        data = {"model": self.model, "prompt": self.prompt, "seconds": self.seconds, "size": self.size}
                        self.logged.emit("Submitting job (multipart)...")
                        r = requests.post(f"{API_BASE}/videos", headers=headers, files=files, data=data, timeout=300)
                        body = self.record(r, "POST /videos")
                else:
                    payload = {"model": self.model, "prompt": self.prompt, "seconds": self.seconds, "size": self.size}
                    self.logged.emit("Submitting job (json)...")
                    r = requests.post(f"{API_BASE}/videos", headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=300)
                    body = self.record(r, "POST /videos")
                if r.status_code not in (200, 201):
                    self.failed.emit(f"Error {r.status_code}\n{pretty(body)}")
                    return
                self.job_id = body.get("id")
                if not self.job_id:
                    self.failed.emit(pretty(body))
                    return
                self.jobid.emit(self.job_id)
                status = body.get("status", "queued")
                prog = body.get("progress", 0) or 0
                self.logged.emit(f"Job id: {self.job_id} [{status}]")
                self.progressed.emit(int(prog))

            start = time.time()
            backoff = max(1, self.poll_every)
            last_status = None
            last_prog = -1
            stuck_99 = 0
            while True:
                if time.time() - start > self.max_minutes * 60:
                    ids = ", ".join(self.req_ids) if self.req_ids else "none"
                    self.failed.emit(f"Timed out waiting for completion. Last request IDs: {ids}")
                    return
                try:
                    pr = requests.get(f"{API_BASE}/videos/{self.job_id}", headers=headers, timeout=120)
                except Exception as e:
                    self.logged.emit(str(e))
                    time.sleep(backoff)
                    backoff = min(15, backoff + 1)
                    continue
                body = self.record(pr, f"GET /videos/{self.job_id}")
                if pr.status_code >= 500:
                    self.logged.emit(f"Poll error {pr.status_code}")
                    self.logged.emit(pretty(body))
                    time.sleep(backoff + random.uniform(0, 0.5))
                    backoff = min(15, backoff * 1.5)
                    continue
                if pr.status_code != 200:
                    self.failed.emit(f"Status poll failed {pr.status_code}\n{pretty(body)}")
                    return
                status = body.get("status", "")
                prog = int(body.get("progress", 0) or 0)
                if status != last_status or prog != last_prog:
                    self.logged.emit(f"Status: {status} {prog}%")
                    self.progressed.emit(prog)
                    last_status, last_prog = status, prog
                if status == "completed":
                    fn = f"{self.job_id}_{body.get('model', self.model)}_{body.get('size', self.size)}_{body.get('seconds', self.seconds)}s.mp4"
                    out_path = self.out_dir / fn
                    self.logged.emit("Downloading video...")
                    dr = requests.get(f"{API_BASE}/videos/{self.job_id}/content", headers=headers, timeout=600, stream=True)
                    dbody = {"streamed": dr.status_code == 200}
                    self.lastresp.emit({"endpoint": f"GET /videos/{self.job_id}/content", "status": dr.status_code, "body": dbody})
                    if dr.status_code != 200:
                        self.failed.emit(f"Download error {dr.status_code}")
                        return
                    with open(out_path, "wb") as f:
                        for chunk in dr.iter_content(chunk_size=1024*256):
                            if chunk:
                                f.write(chunk)
                    self.saved.emit(str(out_path))
                    self.finished.emit()
                    return
                if prog >= 99:
                    stuck_99 += 1
                    if stuck_99 % 10 == 0:
                        dr = requests.get(f"{API_BASE}/videos/{self.job_id}/content", headers=headers, timeout=120, stream=True)
                        self.lastresp.emit({"endpoint": f"GET /videos/{self.job_id}/content", "status": dr.status_code, "body": {"streamed": dr.status_code==200}})
                        if dr.status_code == 200:
                            fn = f"{self.job_id}_{body.get('model', self.model)}_{body.get('size', self.size)}_{body.get('seconds', self.seconds)}s.mp4"
                            out_path = self.out_dir / fn
                            with open(out_path, "wb") as f:
                                for chunk in dr.iter_content(chunk_size=1024*256):
                                    if chunk:
                                        f.write(chunk)
                            self.saved.emit(str(out_path))
                            self.finished.emit()
                            return
                else:
                    stuck_99 = 0
                time.sleep(max(1, self.poll_every))
        except Exception as e:
            self.failed.emit(str(e))
