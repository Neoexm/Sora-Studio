from dataclasses import dataclass
from typing import Optional, Callable
from threading import Thread, Lock, Event, Semaphore
from queue import PriorityQueue
import time
import json
import logging
from pathlib import Path

from sora_core.models import Shot, Profile

logger = logging.getLogger(__name__)

@dataclass
class QueueItem:
    priority: int
    shot: Shot
    profile: Optional[Profile] = None
    cancel_event: Event = None
    progress: float = 0.0
    status_text: str = "Queued"
    
    def __post_init__(self):
        if self.cancel_event is None:
            self.cancel_event = Event()
    
    def __lt__(self, other):
        return self.priority < other.priority

class QueueManager:
    def __init__(self, parallel_jobs: int = 1, state_file: Optional[Path] = None, worker_factory: Optional[Callable] = None):
        self.parallel_jobs = parallel_jobs
        self.state_file = state_file
        self._worker_factory = worker_factory
        self._queue: PriorityQueue[QueueItem] = PriorityQueue()
        self._items: dict[str, QueueItem] = {}
        self._active: dict[str, QueueItem] = {}
        self._completed: list[str] = []
        self._failed: list[str] = []
        self._lock = Lock()
        self._workers: list[Thread] = []
        self._running = False
        self._semaphore = Semaphore(parallel_jobs)
        self._on_status_change: Optional[Callable] = None
        
        if state_file and state_file.exists():
            self._load_state()
        
    def set_parallel(self, n: int) -> None:
        with self._lock:
            old = self.parallel_jobs
            self.parallel_jobs = max(1, n)
            diff = self.parallel_jobs - old
            if diff > 0:
                for _ in range(diff):
                    try:
                        self._semaphore.release()
                    except:
                        pass
            self._save_state()
    
    def enqueue(self, shot: Shot, profile: Optional[Profile] = None, priority: int = 0) -> None:
        with self._lock:
            if shot.id in self._items:
                return
            
            shot.status = "queued"
            item = QueueItem(
                priority=priority,
                shot=shot,
                profile=profile,
                cancel_event=Event()
            )
            self._items[shot.id] = item
            self._queue.put(item)
            self._save_state()
            
            if self._on_status_change:
                self._on_status_change(shot.id, "queued")
            
            logger.info(f"Enqueued shot: {shot.id}")
    
    def reorder(self, shot_ids: list[str]) -> None:
        with self._lock:
            new_queue: PriorityQueue[QueueItem] = PriorityQueue()
            
            for priority, shot_id in enumerate(shot_ids):
                if shot_id in self._items and shot_id not in self._active:
                    item = self._items[shot_id]
                    item.priority = priority
                    new_queue.put(item)
            
            self._queue = new_queue
            self._save_state()
            logger.info(f"Reordered queue: {len(shot_ids)} items")
    
    def cancel(self, shot_id: str) -> bool:
        with self._lock:
            if shot_id in self._items:
                item = self._items[shot_id]
                item.cancel_event.set()
                item.shot.status = "cancelled"
                
                if self._on_status_change:
                    self._on_status_change(shot_id, "cancelled")
                
                self._save_state()
                logger.info(f"Cancelled shot: {shot_id}")
                return True
        
        return False
    
    def get_all_items(self) -> list[tuple[str, Shot, int, str]]:
        with self._lock:
            items = []
            for shot_id, item in self._items.items():
                status = "active" if shot_id in self._active else item.shot.status
                items.append((shot_id, item.shot, item.priority, status))
            return sorted(items, key=lambda x: x[2])
    
    def get_queue_status(self) -> dict:
        with self._lock:
            queued = [sid for sid, item in self._items.items() 
                     if sid not in self._active and item.shot.status == "queued"]
            return {
                "queued": queued,
                "active": list(self._active.keys()),
                "completed": self._completed.copy(),
                "failed": self._failed.copy(),
                "total": len(self._items)
            }
    
    def set_status_callback(self, callback: Callable) -> None:
        self._on_status_change = callback
    
    def update_status(self, shot_id: str, status: str, progress: float = 0.0) -> None:
        with self._lock:
            if shot_id in self._items:
                self._items[shot_id].shot.status = status
                self._items[shot_id].progress = progress
                if self._on_status_change:
                    self._on_status_change(shot_id, status)
                self._save_state()
    
    def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        for i in range(self.parallel_jobs):
            worker = Thread(target=self._worker_loop, daemon=True, name=f"QueueWorker-{i}")
            worker.start()
            self._workers.append(worker)
        logger.info(f"Started queue manager with {self.parallel_jobs} workers")
    
    def stop(self) -> None:
        self._running = False
        for worker in self._workers:
            if worker.is_alive():
                worker.join(timeout=2.0)
        self._workers.clear()
        logger.info("Stopped queue manager")
    
    def _worker_loop(self) -> None:
        while self._running:
            item = None
            
            try:
                item = self._queue.get(timeout=0.5)
            except:
                continue
            
            if not item:
                continue
            
            self._semaphore.acquire()
            
            try:
                with self._lock:
                    self._active[item.shot.id] = item
                    item.shot.status = "processing"
                    if self._on_status_change:
                        self._on_status_change(item.shot.id, "processing")
                
                if item.profile:
                    self._apply_rate_limit(item.profile)
                
                if item.cancel_event.is_set():
                    raise Exception("Cancelled")
                
                if self._worker_factory:
                    success, error_msg = self._worker_factory(item.shot)
                    if not success:
                        raise Exception(error_msg or "Worker failed")
                else:
                    logger.warning(f"No worker factory - shot {item.shot.id} skipped")
                
                item.shot.status = "completed"
                
                with self._lock:
                    if item.shot.id in self._active:
                        del self._active[item.shot.id]
                    self._completed.append(item.shot.id)
                    if self._on_status_change:
                        self._on_status_change(item.shot.id, "completed")
                
                logger.info(f"Completed shot: {item.shot.id}")
                
            except Exception as e:
                logger.error(f"Shot failed: {item.shot.id} - {e}")
                with self._lock:
                    if item.shot.id in self._active:
                        del self._active[item.shot.id]
                    self._failed.append(item.shot.id)
                    item.shot.status = "failed"
                    if self._on_status_change:
                        self._on_status_change(item.shot.id, "failed")
            finally:
                self._semaphore.release()
                self._save_state()
    
    def clear_completed(self) -> None:
        with self._lock:
            to_remove = [
                sid for sid, item in self._items.items()
                if item.shot.status in ("completed", "failed", "cancelled")
            ]
            for shot_id in to_remove:
                del self._items[shot_id]
            self._save_state()
            logger.info(f"Cleared {len(to_remove)} completed items")
    
    def _apply_rate_limit(self, profile: Profile) -> None:
        if profile.backoff_seconds > 0:
            time.sleep(profile.backoff_seconds)
    
    def _save_state(self) -> None:
        if not self.state_file:
            return
        
        try:
            data = {
                "parallel_jobs": self.parallel_jobs,
                "items": [
                    {
                        "priority": item.priority,
                        "shot": {
                            "id": item.shot.id,
                            "model": item.shot.model,
                            "width": item.shot.width,
                            "height": item.shot.height,
                            "duration_s": item.shot.duration_s,
                            "prompt": item.shot.prompt,
                            "ref_images": item.shot.ref_images,
                            "status": item.shot.status,
                            "job_id": item.shot.job_id,
                            "output_path": item.shot.output_path,
                            "meta": item.shot.meta,
                            "created_at": item.shot.created_at
                        }
                    }
                    for item in sorted(self._items.values(), key=lambda x: x.priority)
                ],
                "completed": self._completed,
                "failed": self._failed
            }
            
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save queue state: {e}")
    
    def _load_state(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.parallel_jobs = data.get("parallel_jobs", 1)
            self._completed = data.get("completed", [])
            self._failed = data.get("failed", [])
            
            for item_data in data.get("items", []):
                shot_data = item_data["shot"]
                shot = Shot(**shot_data)
                
                if shot.status in ("completed", "cancelled", "failed"):
                    continue
                
                shot.status = "queued"
                
                item = QueueItem(
                    priority=item_data["priority"],
                    shot=shot,
                    cancel_event=Event()
                )
                self._items[shot.id] = item
                self._queue.put(item)
            
            logger.info(f"Loaded {len(self._items)} items from queue state")
        except Exception as e:
            logger.error(f"Failed to load queue state: {e}")
