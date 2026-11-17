"""Bound password CPU work separately from general web threads and database sessions."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


class PasswordCapacityFull(Exception):
    pass


class PasswordCapacity:
    def __init__(self, workers=1, max_pending=512):
        if not 1 <= workers <= 4 or not workers <= max_pending <= 512:
            raise ValueError("Password workers must be 1..4 and pending capacity workers..512.")
        self._slots = threading.BoundedSemaphore(max_pending)
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hrms-password")

    async def verify(self, function, password, stored_hash):
        return await self.run(function, password, stored_hash)

    async def run(self, function, *args):
        if not self._slots.acquire(blocking=False):
            raise PasswordCapacityFull()
        try:
            work = self._executor.submit(function, *args)
        except BaseException:
            self._slots.release()
            raise
        work.add_done_callback(lambda _future: self._slots.release())
        return await asyncio.wrap_future(work)

    def close(self):
        self._executor.shutdown(wait=True, cancel_futures=True)
