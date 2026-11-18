"""Batch job management with a worker pool."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..core.exceptions import JobError


@dataclass
class JobResult:
    input_path: str
    output_path: Optional[str] = None
    ok: bool = False
    error: Optional[str] = None
    duration_ms: int = 0
    warnings: List[str] = field(default_factory=list)


class JobQueue:
    def __init__(self, workers: Optional[int] = None):
        self.workers = workers or max(1, (os.cpu_count() or 4) - 1)
        self._executor = ThreadPoolExecutor(max_workers=self.workers)
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run_batch(
        self,
        items: List[Dict],
        worker_fn: Callable[[Dict], JobResult],
        on_progress: Optional[Callable[[int, int, JobResult], None]] = None,
    ) -> List[JobResult]:
        results: List[JobResult] = []
        total = len(items)
        done = 0
        futures = {self._executor.submit(worker_fn, item): item for item in items}
        try:
            for fut in as_completed(futures):
                if self._cancel.is_set():
                    for f in futures:
                        f.cancel()
                    raise JobError("Batch cancelled")
                try:
                    r = fut.result()
                except Exception as e:
                    r = JobResult(input_path=str(futures[fut].get("input", "?")), ok=False, error=str(e))
                results.append(r)
                done += 1
                if on_progress:
                    on_progress(done, total, r)
        finally:
            pass
        return results

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
