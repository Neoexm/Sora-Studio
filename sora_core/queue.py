from dataclasses import dataclass, field
from typing import Optional, Callable
from queue import Queue, Empty
from threading import Thread, Lock, Event
import time
import logging

from sora_core.models import Shot, Profile

logger = logging.getLogger(__name__)

@dataclass
class QueuedShot:
    shot: Shot
    profile: Optional[Profile] = None
    worker_callback: Optional[Callable] = None
    cancel_event: Optional[Event] = None
    progress: float = 0.0
    status_text: str = "Queued"
    
class QueueManager:
    def __init__(self, parallel_jobs: int = 1):
        self.parallel_jobs = parallel_jobs
        self.queue: list[QueuedShot] = []
        self.active: dict[str, QueuedShot] = {}
        self.completed: list[str] = []
        self.failed: list[str] = []
        self.lock = Lock()
        self.workers: list[Thread] = []
        self.running = False
        self.state_file: Optional[str] = None
        
    def set_parallel(self, n: int) -> None:
        with self.lock:
            self.parallel_jobs = max(1, n)
    
    def enqueue(self, shot: Shot, profile: Optional[Profile] = None, 
                worker_callback: Optional[Callable] = None) -> None:
        with self.lock:
            queued = QueuedShot(
                shot=shot,
                profile=profile,
                worker_callback=worker_callback,
                cancel_event=Event()
            )
            self.queue.append(queued)
            logger.info(f"Enqueued shot: {shot.id}")
    
    def reorder(self, shot_ids: list[str]) -> None:
        with self.lock:
            id_to_shot = {qs.shot.id: qs for qs in self.queue}
            new_queue = []
            for shot_id in shot_ids:
                if shot_id in id_to_shot:
                    new_queue.append(id_to_shot[shot_id])
            self.queue = new_queue
            logger.info(f"Reordered queue: {len(new_queue)} items")
    
    def cancel(self, shot_id: str) -> bool:
        with self.lock:
            for qs in self.queue:
                if qs.shot.id == shot_id:
                    self.queue.remove(qs)
                    logger.info(f"Cancelled queued shot: {shot_id}")
                    return True
            
            if shot_id in self.active:
                qs = self.active[shot_id]
                if qs.cancel_event:
                    qs.cancel_event.set()
                logger.info(f"Cancelling active shot: {shot_id}")
                return True
        
        return False
    
    def get_queue_status(self) -> dict:
        with self.lock:
            return {
                "queued": [qs.shot.id for qs in self.queue],
                "active": list(self.active.keys()),
                "completed": self.completed.copy(),
                "failed": self.failed.copy(),
                "total": len(self.queue) + len(self.active)
            }
    
    def start(self) -> None:
        if self.running:
            return
        
        self.running = True
        for i in range(self.parallel_jobs):
            worker = Thread(target=self._worker_loop, daemon=True, name=f"QueueWorker-{i}")
            worker.start()
            self.workers.append(worker)
        logger.info(f"Started queue manager with {self.parallel_jobs} workers")
    
    def stop(self) -> None:
        self.running = False
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=2.0)
        self.workers.clear()
        logger.info("Stopped queue manager")
    
    def _worker_loop(self) -> None:
        while self.running:
            queued_shot = None
            
            with self.lock:
                if len(self.active) < self.parallel_jobs and self.queue:
                    queued_shot = self.queue.pop(0)
                    self.active[queued_shot.shot.id] = queued_shot
            
            if not queued_shot:
                time.sleep(0.1)
                continue
            
            try:
                if queued_shot.profile:
                    self._apply_rate_limit(queued_shot.profile)
                
                if queued_shot.cancel_event and queued_shot.cancel_event.is_set():
                    raise Exception("Cancelled")
                
                queued_shot.status_text = "Processing"
                
                if queued_shot.worker_callback:
                    queued_shot.worker_callback(queued_shot.shot, queued_shot.cancel_event)
                
                with self.lock:
                    if queued_shot.shot.id in self.active:
                        del self.active[queued_shot.shot.id]
                    self.completed.append(queued_shot.shot.id)
                
                logger.info(f"Completed shot: {queued_shot.shot.id}")
                
            except Exception as e:
                logger.error(f"Shot failed: {queued_shot.shot.id} - {e}")
                with self.lock:
                    if queued_shot.shot.id in self.active:
                        del self.active[queued_shot.shot.id]
                    self.failed.append(queued_shot.shot.id)
    
    def _apply_rate_limit(self, profile: Profile) -> None:
        if profile.backoff_seconds > 0:
            time.sleep(profile.backoff_seconds)
    
    def save_state(self, path: str) -> None:
        import json
        with self.lock:
            state = {
                "queued": [qs.shot.id for qs in self.queue],
                "active": list(self.active.keys()),
                "completed": self.completed,
                "failed": self.failed
            }
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved queue state to {path}")
    
    def load_state(self, path: str) -> dict:
        import json
        try:
            with open(path, "r") as f:
                state = json.load(f)
            logger.info(f"Loaded queue state from {path}")
            return state
        except Exception as e:
            logger.error(f"Failed to load queue state: {e}")
            return {}
