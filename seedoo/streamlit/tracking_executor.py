import logging
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from threading import Lock, Thread
import time
import functools
import ctypes
import threading
import inspect

class ThreadInterrupted(Exception):
    pass

# Helper function to send an exception to the thread to stop it
def _async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("Invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")



def safe_name(fn):
    if isinstance(fn, functools.partial):
        return fn.func.__name__
    return fn.__name__

class TrackingThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=None, thread_name_prefix='', timeout=10):
        super().__init__(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)
        self._futures = []
        self._timeout = timeout
        self._monitor_thread = Thread(target=self._monitor)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()


    def submit(self, fn, *args, **kwargs):
        wrapped_fn = self._wrap_fn(fn)
        future = super().submit(wrapped_fn, *args, **kwargs)
        with self._lock:
            future._start_time = time.time()
            self._futures.append((future, wrapped_fn))
        self.logger.debug(f'Submitting task: {safe_name(fn)} with args: {args} and kwargs: {kwargs}')
        return future

    def _wrap_fn(self, fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            wrapped.thread_id = threading.get_ident()
            wrapped._start_time = time.time()
            try:
                delay = (time.time() - wrapped._start_time) * 1000
                (self.logger.info if delay < 5 else self.logger.warning)(f"Submit delay: {delay}")
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                raise e
        return wrapped



    def _monitor(self):
        while True:
            self.logger.debug('Checking tasks for timeout...')
            ratio = self.active_threads / self._max_workers
            (self.logger.debug if self.active_threads < 2 else self.logger.info)(f'{self._thread_name_prefix} executor, active threads: {self.active_threads}')

            (self.logger.warning if ratio > 0.5 else self.logger.debug)(f'{self._thread_name_prefix} executor utilization: {ratio:.2%}')

            with self._lock:
                for future, wrapped_fn in self._futures:
                    self.logger.debug(f'Checking task: {future}')
                    duration = (time.time() - future._start_time)
                    if future.running():
                        if duration > self._timeout:
                            self.logger.critical(f'Task {future} is running for {duration} longer than {self._timeout} seconds and will be cancelled.')
                            if wrapped_fn.thread_id:
                                _async_raise(wrapped_fn.thread_id, ThreadInterrupted)
                            else:
                                self.logger.critical(f"Task {future} can not be canceled because it doesn't have a thread id")

                        elif duration > self._timeout * 0.98:
                            ratio = duration / self._timeout
                            self.logger.warning(
                                f'Task {future} is running for {duration} which is {ratio:.2%} of the timeout and will soon will be cancelled')

                # Clean up completed futures
                self._futures = [(f, wrapped_fn) for f, wrapped_fn in self._futures if not f.done()]
            time.sleep(5)

    @property
    def active_threads(self):
        with self._lock:
            return len(self._futures)

    @property
    def idling_threads(self):
        return self._max_workers - self.active_threads

# Example usage
def task(n):

    try:
        time.sleep(n)
        return n
    except ThreadInterrupted as exc:
        print('ThreadInterrupted called!')
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    max_workers = 5
    timeout =  2 # Set timeout for task execution
    with TrackingThreadPoolExecutor(max_workers=max_workers, timeout=timeout) as executor:
        futures = [executor.submit(task, i) for i in range(10)]
        for future in as_completed(futures):
            if future.cancelled():
                print(f'Task was cancelled due to timeout')
            else:
                print(f'Completed task with result: {future.result()}')
            print(f'Active threads: {executor.active_threads}')
            print(f'Idling threads: {executor.idling_threads}')
