import logging
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from threading import Lock, Thread
import time
import functools


def safe_name(fn):
    if isinstance(fn, functools.partial):
        return fn.func.__name__
    return fn.__name__

class TrackingThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=None, thread_name_prefix='', timeout=10):
        super().__init__(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)
        self._active_threads = 0
        self._futures = []
        self._timeout = timeout
        self._monitor_thread = Thread(target=self._monitor)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def submit(self, fn, *args, **kwargs):
        with self._lock:
            self._active_threads += 1
        self.logger.debug(f'Submitting task: {safe_name(fn)} with args: {args} and kwargs: {kwargs}')
        future = super().submit(self._wrapped_fn, fn, *args, **kwargs)
        future._start_time = time.time()  # Store the start time
        with self._lock:
            self._futures.append(future)
        return future

    def _wrapped_fn(self, fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        finally:
            with self._lock:
                self._active_threads -= 1
                self.logger.debug(f'Task {safe_name(fn)} completed.')
        return result

    def _monitor(self):
        while True:
            self.logger.debug('Checking tasks for timeout...')
            self.logger.debug(f'{self._thread_name_prefix} executor, active threads: {self.active_threads}')
            ratio = self.active_threads / self._max_workers


            (self.logger.warning if ratio > 0.5 else self.logger.debug)(f'{self._thread_name_prefix} executor utilization: {ratio:.2%}')

            with self._lock:
                for future in self._futures:
                    self.logger.debug(f'Checking task: {future}')
                    duration = (time.time() - future._start_time)
                    if future.running():
                        if duration > self._timeout:
                            self.logger.critical(f'Task {future} is running for {duration} longer than {self._timeout} seconds and will be cancelled.')
                            future.cancel()
                        if duration > self._timeout * 0.5:
                            ratio = duration / self._timeout
                            self.logger.warning(
                                f'Task {future} is running for {duration} which is {ratio:.2%} of the timeout and will soon will be cancelled')

                # Clean up completed futures
                self._futures = [f for f in self._futures if not f.done()]
            time.sleep(1)

    @property
    def active_threads(self):
        with self._lock:
            return self._active_threads

    @property
    def idling_threads(self):
        return self._max_workers - self.active_threads

# Example usage
def task(n):
    time.sleep(n)
    return n

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    max_workers = 5
    timeout = 3  # Set timeout for task execution
    with TrackingThreadPoolExecutor(max_workers=max_workers, timeout=timeout) as executor:
        futures = [executor.submit(task, i) for i in range(10)]
        for future in as_completed(futures):
            if future.cancelled():
                print(f'Task was cancelled due to timeout')
            else:
                print(f'Completed task with result: {future.result()}')
            print(f'Active threads: {executor.active_threads}')
            print(f'Idling threads: {executor.idling_threads}')
