import asyncio
import logging
import multiprocessing
import websockets
import websockets.exceptions
import threading
import msgpack
import json
from seedoo.streamlit.tracking_executor import TrackingThreadPoolExecutor, safe_name
import time
import os
import traceback
import sys
from functools import partial
import numpy as np
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import heapq
import weakref
from concurrent.futures import _base
from typing import Optional, Callable, Dict, Any, Tuple

SEEDOO_SEMAPHORE_NAME = 'seedoo_ux_semaphore'
error_auth_text = 'user not authenticated'
user_id_default = 'user_id_default'


class UpdatableHeap:
    """Priority queue with ability to update priorities"""
    def __init__(self):
        # Heap stores (priority, key) pairs
        self.heap = []
        self.key_index_map = {}  # Maps key -> index in heap

    def push(self, priority, key):
        """
        Insert a new (priority, key) into the heap.
        If the key already exists, update its priority instead.
        """
        if key in self.key_index_map:
            self.update(priority, key)
        else:
            # Manual push to preserve index consistency
            self.heap.append((priority, key))
            idx = len(self.heap) - 1
            self.key_index_map[key] = idx
            self._bubble_up(idx)

    def pop(self):
        """
        Remove and return the (priority, key) pair with the smallest priority.
        Raises KeyError if heap is empty.
        """
        if not self.heap:
            raise KeyError('Pop from empty heap')

        last_idx = len(self.heap) - 1
        # Swap root with last and remove it
        self._swap(0, last_idx)
        priority, key = self.heap.pop()
        del self.key_index_map[key]

        if self.heap:
            self._bubble_down(0)
        return priority, key

    def update(self, new_priority, key, strict=False):
        """
        Update the priority of an existing key.
        If strict is True, raises KeyError if key is not found.
        If strict is False (default), inserts the key if not present.
        """
        idx = self.key_index_map.get(key)
        if idx is None:
            if strict:
                raise KeyError(f"Key {key} not found in heap for update")
            self.push(new_priority, key)
            return

        # Defensive consistency check
        if idx >= len(self.heap) or self.heap[idx][1] != key:
            raise RuntimeError(f"Inconsistent heap state for key: {key}")

        old_priority, _ = self.heap[idx]
        self.heap[idx] = (new_priority, key)
        if new_priority < old_priority:
            self._bubble_up(idx)
        else:
            self._bubble_down(idx)

    def _bubble_up(self, idx):
        while idx > 0:
            parent = (idx - 1) >> 1
            if self.heap[idx][0] < self.heap[parent][0]:
                self._swap(idx, parent)
                idx = parent
            else:
                break

    def _bubble_down(self, idx):
        size = len(self.heap)
        while True:
            left = 2 * idx + 1
            right = 2 * idx + 2
            smallest = idx

            if left < size and self.heap[left][0] < self.heap[smallest][0]:
                smallest = left
            if right < size and self.heap[right][0] < self.heap[smallest][0]:
                smallest = right

            if smallest == idx:
                break

            self._swap(idx, smallest)
            idx = smallest

    def _swap(self, i, j):
        """Swap elements at indices i and j, and update key_index_map accordingly."""
        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]
        self.key_index_map[self.heap[i][1]] = i
        self.key_index_map[self.heap[j][1]] = j

    def __len__(self):
        return len(self.heap)

    def __contains__(self, key):
        return key in self.key_index_map

    def __bool__(self):
        return bool(self.heap)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.astype(int).tolist()
        return super(CustomJSONEncoder, self).default(obj)


class PriorityTrackingThreadPoolExecutor(TrackingThreadPoolExecutor):
    """Thread pool executor with priority queue instead of FIFO"""
    
    class _WorkItem:
        """Wrapper for work items with priority tracking"""
        def __init__(self, future, fn, args, kwargs, submit_time):
            self.future = future
            self.fn = fn
            self.args = args
            self.kwargs = kwargs
            self.submit_time = submit_time
            
        def run(self):
            if not self.future.set_running_or_notify_cancel():
                return
            try:
                result = self.fn(*self.args, **self.kwargs)
            except BaseException as exc:
                self.future.set_exception(exc)
                self = None  # Break reference cycle
            else:
                self.future.set_result(result)
                
    def __init__(self, max_workers=None, thread_name_prefix='',
                 timeout=None, max_age_ms=10000, recent_bonus_ms=2000,
                 max_abandoned_ratio=0.5):
        # Priority queue parameters
        self._max_age_ms = max_age_ms
        self._recent_bonus_ms = recent_bonus_ms
        self._max_abandoned_ratio = max_abandoned_ratio
        
        # Initialize parent
        super().__init__(max_workers, thread_name_prefix, timeout)
        
        # Replace work queue with priority version
        self._work_heap = UpdatableHeap()
        self._work_queue_lock = threading.Lock()
        self._work_available = threading.Condition(self._work_queue_lock)
        self._pending_work_items = {}
        self._next_item_id = 0
        
        # Track abandoned threads
        self._abandoned_threads = weakref.WeakSet()
        self._thread_timeout_stats = {
            'total_timeouts': 0,
            'active_abandoned': 0
        }
        
        # Circuit breaker
        self._consecutive_timeouts = 0
        self._circuit_breaker_threshold = 10
        
        # Initialize threads
        self._shutdown = False
        self._shutdown_lock = threading.Lock()
        self._threads = set()
        
        # Start initial threads
        for _ in range(min(self._max_workers, 1)):
            self._start_worker_thread()
    
    def _start_worker_thread(self):
        """Start a new worker thread"""
        thread_name = f"{self._thread_name_prefix}_{len(self._threads)}"
        t = threading.Thread(
            name=thread_name,
            target=self._worker,
            daemon=True
        )
        t.start()
        self._threads.add(t)
    
    def _ensure_worker_threads(self):
        """Ensure we have enough worker threads"""
        # Remove dead threads
        self._threads = {t for t in self._threads if t.is_alive()}
        
        # Start new threads if needed
        while len(self._threads) < self._max_workers and len(self._work_heap) > 0:
            self._start_worker_thread()
        
    def _calculate_priority(self, submit_time):
        """Calculate priority - lower number = higher priority"""
        age_ms = (time.time() - submit_time) * 1000
        
        if age_ms < self._recent_bonus_ms:
            # Recent items get negative priority (high priority)
            return -self._recent_bonus_ms + age_ms
        elif age_ms > self._max_age_ms:
            # Old items get promoted (large negative = high priority)
            return -1000000 - age_ms  # Ensure old operations execute
        else:
            # Normal aging
            return age_ms - self._recent_bonus_ms
    
    def submit(self, fn, *args, **kwargs):
        """Submit with priority tracking"""
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')
            
            # Check abandoned thread limit
            max_abandoned = max(1, int(self._max_workers * self._max_abandoned_ratio))
            if len(self._abandoned_threads) >= max_abandoned:
                raise RuntimeError(
                    f"Thread pool exhausted: {len(self._abandoned_threads)} "
                    f"abandoned threads (max: {max_abandoned})"
                )
            
            # Check circuit breaker
            if self._consecutive_timeouts >= self._circuit_breaker_threshold:
                raise RuntimeError(
                    f"Circuit breaker open: {self._consecutive_timeouts} consecutive timeouts"
                )
                
            f = _base.Future()
            submit_time = time.time()
            w = self._WorkItem(f, fn, args, kwargs, submit_time)
            
            # Add to priority queue
            with self._work_queue_lock:
                item_id = self._next_item_id
                self._next_item_id += 1
                
                priority = self._calculate_priority(submit_time)
                self._work_heap.push(priority, item_id)
                self._pending_work_items[item_id] = w
                
                self._work_available.notify()
                
            # Ensure we have worker threads
            self._ensure_worker_threads()
            return f
    
    def _get_next_work_item(self):
        """Get next work item from priority queue"""
        with self._work_queue_lock:
            while not self._work_heap and not self._shutdown:
                self._work_available.wait()
                
            if self._shutdown:
                return None
                
            # Update priorities for aging
            current_time = time.time()
            for priority, item_id in list(self._work_heap.heap):
                if item_id in self._pending_work_items:
                    item = self._pending_work_items[item_id]
                    new_priority = self._calculate_priority(item.submit_time)
                    if new_priority != priority:
                        self._work_heap.update(new_priority, item_id)
            
            # Get highest priority item
            priority, item_id = self._work_heap.pop()
            return self._pending_work_items.pop(item_id)
    
    def _worker(self):
        """Override worker to use priority queue"""
        try:
            while True:
                work_item = self._get_next_work_item()
                
                if work_item is None:
                    break
                    
                # Check if this was abandoned due to timeout
                if work_item.future in self._abandoned_threads:
                    self._thread_timeout_stats['active_abandoned'] += 1
                
                work_item.run()
                
                # Clean up if it was abandoned
                if work_item.future in self._abandoned_threads:
                    self._abandoned_threads.discard(work_item.future)
                    self._thread_timeout_stats['active_abandoned'] -= 1
                    
                del work_item
                
        except BaseException:
            _base.LOGGER.critical('Exception in worker', exc_info=True)
    
    def mark_abandoned(self, future):
        """Mark a future as abandoned due to timeout"""
        self._abandoned_threads.add(future)
        self._thread_timeout_stats['total_timeouts'] += 1
        self._consecutive_timeouts += 1
        
    def mark_success(self):
        """Reset consecutive timeout counter on success"""
        self._consecutive_timeouts = 0
        
    def get_stats(self):
        """Get executor statistics"""
        with self._work_queue_lock:
            queue_size = len(self._work_heap)
            
            # Sample oldest items
            oldest_items = []
            for priority, item_id in self._work_heap.heap[:5]:
                if item_id in self._pending_work_items:
                    item = self._pending_work_items[item_id]
                    age_ms = (time.time() - item.submit_time) * 1000
                    oldest_items.append({
                        'age_ms': age_ms,
                        'priority': priority
                    })
            
        return {
            'queue_size': queue_size,
            'oldest_items': oldest_items,
            'active_threads': len(self._threads),
            'abandoned_threads': len(self._abandoned_threads),
            'total_timeouts': self._thread_timeout_stats['total_timeouts'],
            'consecutive_timeouts': self._consecutive_timeouts
        }
    
    def shutdown(self, wait=True, *, cancel_futures=False):
        """Shutdown the executor"""
        with self._shutdown_lock:
            self._shutdown = True
            # Notify all waiting threads
            with self._work_queue_lock:
                self._work_available.notify_all()
        
        if wait:
            for t in self._threads:
                t.join()
                
        # Call parent shutdown
        super().shutdown(wait=wait, cancel_futures=cancel_futures)


class WebSocketServer:
    _instance = None

    @classmethod
    def instance(cls, st):
        if WebSocketServer._instance is None:
            port = int(os.environ.get('SEEDOO_WEBSOCKET_EVENT_PORT', '9898'))
            forwarded_port = os.environ.get('SEEDOO_WEBSOCKET_EVENT_PORT_FORWARDED', '')
            host = os.environ.get('SEEDOO_WEBSOCKET_EVENT_HOST', 'localhost')
            if forwarded_port:
                port = int(forwarded_port)

            WebSocketServer._instance = WebSocketServer(host, port=port, ctx=st)
            WebSocketServer._instance.start_server()

        return WebSocketServer._instance

    def __init__(self, host="localhost", port=9897, ctx=None):
        self.host = host
        self.logger = logging.getLogger(__name__)
        self.port = port
        self.callbacks = {}
        self.timeout = 130
        self.paths = {}
        self.is_running = False
        self.initialized_contexts = False
        self.tokens_store = None
        self.running_server = None
        self.loop = None  # Will be set when server starts
        num_cpus = multiprocessing.cpu_count()
        
        # Check if priority queue is enabled
        use_priority_queue = os.environ.get('SEEDOO_ENABLE_PRIORITY_QUEUE', 'true').lower() == 'true'
        thread_pool_size = int(os.environ.get('SEEDOO_THREAD_POOL_SIZE', '40'))
        max_age_ms = int(os.environ.get('SEEDOO_PRIORITY_MAX_AGE_MS', '10000'))
        default_timeout = float(os.environ.get('SEEDOO_DEFAULT_CALLBACK_TIMEOUT', '0'))
        
        if use_priority_queue:
            self.thread_pool_executor = PriorityTrackingThreadPoolExecutor(
                max_workers=thread_pool_size,
                thread_name_prefix="PriorityPool",
                timeout=180,
                max_age_ms=max_age_ms,
                recent_bonus_ms=2000,
                max_abandoned_ratio=0.5
            )
            self.logger.info(f"Using priority queue executor with {thread_pool_size} threads")
        else:
            # Fallback to original but with configurable size
            self.thread_pool_executor = TrackingThreadPoolExecutor(
                max_workers=thread_pool_size,
                timeout=180
            )
            self.logger.info(f"Using standard executor with {thread_pool_size} threads")
        
        self.default_callback_timeout = default_timeout
        self.clients = {}  # Keep track of connected clients

        if ctx is not None:
            for thread in threading.enumerate():
                if thread.name.startswith(self.thread_pool_executor._thread_name_prefix):
                    add_script_run_ctx(thread, ctx)

    async def handler(self, websocket, path):
        try:
            start = time.time()
            self.logger.info(f"CONNECTED {path}")
            if path in self.clients:
                self.logger.warning(f'Path {path} is already in clients!')
            self.clients[path] = websocket
            websocket.is_component_ready = False
            route = ''

            if path.startswith('/ws/functions') or path.startswith('/wss/functions'):
                route = 'handle_function_paths'
                await self.handle_function_paths(websocket, path)
            else:
                route = 'handle_other_paths'
                await self.handle_other_paths(websocket, path)

            end = time.time()
            duration = (end - start) * 1000
            self.logger.info(f'HANDLER duration: {duration}  for path: {path} ms, route: {route}')
        except Exception as exc:
            self.logger.critical('Error in handler')
            self.logger.exception('Error in handler')

    async def handle_function_paths(self, websocket, path):
        while True:
            target_function_name = ''
            try:
                target_function = os.path.basename(path)
                start = time.time()
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                end = time.time()

                recv_duration = (end - start) * 1000
                self.logger.info(f'recv duration: {recv_duration} ms')

                if target_function not in self.paths:
                    self.logger.critical(f'Target requested function: {target_function} is not registered.')
                else:
                    target_function = self.paths[target_function]
                    asyncio.create_task(self.execute_target_function(websocket, target_function, message, path))

            except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
                self.logger.warning(f'Error in communicating with socket for function: {target_function_name}')
                break
            except asyncio.TimeoutError:
                self.logger.debug('Asyncio timeout')
                if not websocket.open:
                    self.logger.warning('Closing socket - Asyncio timeout')
                    break
            except Exception as exc:
                self.logger.exception(f'Error in socket handler: {exc}')

    async def error(self, websocket, error_auth_text):
        self.logger.warning(f'{error_auth_text}')
        await asyncio.wait_for(
            websocket.send(json.dumps({'event': 'message', 'data': {'message': error_auth_text, 'type': 'error'}})),
            timeout=self.timeout)

    async def execute_target_function(self, websocket, target_function, message, path):
        target_function_name = safe_name(target_function)
        id = 'default_this_means_did not load from message'
        try:
            self.logger.info(f'Executing function: {target_function_name}')
            start = time.time()
            message_data = json.loads(message)
            if 'session_id' in message_data and self.tokens_store:
                message_data['session_state'] = self.tokens_store.get_session_state(message_data['session_id'])
            if 'user_id' in message_data and self.tokens_store:
                message_data['user_state'] = self.tokens_store.get_user_state(message_data['user_id'])
            duration = (time.time() - start) * 1000
            (self.logger.warning if duration > 50 else self.logger.debug)(f'message data json load: {duration} ms')

            start = time.time()

            try:
                async def start_function():
                    response = await asyncio.get_running_loop().run_in_executor(self.thread_pool_executor,
                                                                                target_function, message_data)
                    await asyncio.wait_for(self.send_response(websocket, message_data, response),
                                           timeout=self.timeout)

                if self.tokens_store:
                    if 'accessToken' in message_data:
                        accessToken = message_data['accessToken']
                        if self.tokens_store.check_valid(accessToken):
                            await start_function()
                        else:
                            await self.error(websocket, error_auth_text)
                    else:
                        await self.error(websocket, 'no accessToken')
                else:
                    await start_function()
            except asyncio.TimeoutError:
                self.logger.critical(f'Timeout in sending respone back to client!, path: {path}')
                if not websocket.open:
                    self.logger.warning('Closing socket - Asyncio timeout')
                    if path in self.clients:
                        self.clients.pop(path)

            duration = (time.time() - start) * 1000
            (self.logger.warning if duration > 500 else self.logger.debug)(
                f'function {target_function_name} executed for {duration} ms')

        except Exception as e:
            try:
                self.logger.exception(
                    f'Error in calling target function: {target_function_name} on path {path}, message was: {message}')
                # Extracting stack trace
                exc_type, exc_value, exc_traceback = sys.exc_info()

                # Extracting stack trace
                tb = traceback.extract_tb(exc_traceback)
                # Finding the first stack frame that belongs to this module

                # Get the last frame in the traceback
                deepest_frame = tb[-1]
                function_name = deepest_frame.name
                line_number = deepest_frame.lineno

                message = f"{exc_value} (FN: {function_name}, LN:{line_number})"

                error_message_data = {'id': id, 'event': 'message', 'data': {'message': message, 'type': 'error'}}
                try:
                    await asyncio.wait_for(self.send_response(websocket, {}, error_message_data), timeout=10)
                except asyncio.TimeoutError:
                    if not websocket.open:
                        self.logger.warning('Closing socket - Asyncio timeout')
                        if path in self.clients:
                            self.clients.pop(path)

            except Exception as exc:
                self.logger.critical('Error in handling exception!!!')
                self.logger.exception('CRITICAL!! Error in handling exception!!!')

    async def send_response(self, websocket, message_data, response):
        if message_data.get('binary'):
            self.logger.info('Sending binary response')
            binary_data = msgpack.packb(response, use_bin_type=True)
            await websocket.send(binary_data)
        else:
            self.logger.info('Sending text json response')
            start = time.time()
            # Parse JSON directly without thread pool
            text_response = json.dumps(response, cls=CustomJSONEncoder)
            json_delay = (time.time() - start) * 1000
            (self.logger.debug if json_delay < 20 else self.logger.warning)(
                f'_send_data_async json dumps took delay is {json_delay} ms')

            await websocket.send(text_response)

    async def _execute_callback_with_timeout(self, callback, message, timeout=None):
        """Execute callback with optional timeout"""
        if timeout and timeout > 0:
            # Submit to executor and wrap in asyncio
            future = self.thread_pool_executor.submit(callback, message)
            try:
                result = await asyncio.wait_for(
                    asyncio.wrap_future(future),
                    timeout=timeout
                )
                # Mark success if using priority executor
                if hasattr(self.thread_pool_executor, 'mark_success'):
                    self.thread_pool_executor.mark_success()
                return result
            except asyncio.TimeoutError:
                self.logger.error(f'Callback timed out after {timeout}s')
                # Mark as abandoned if using priority executor
                if hasattr(self.thread_pool_executor, 'mark_abandoned'):
                    self.thread_pool_executor.mark_abandoned(future)
                raise
        else:
            # No timeout - normal execution
            result = await asyncio.get_running_loop().run_in_executor(
                self.thread_pool_executor, callback, message
            )
            # Mark success if using priority executor
            if hasattr(self.thread_pool_executor, 'mark_success'):
                self.thread_pool_executor.mark_success()
            return result
    
    def removeByKeyFragment(self, full_key, user_id=user_id_default):
        if user_id not in self.callbacks:
            return

        keyFragment = "/".join(full_key.split("/")[2:])
        keysToDelete = [key for key in self.callbacks[user_id] if keyFragment in key]

        for key in keysToDelete:
            self.callbacks[user_id].pop(key, None)
            self.logger.info(f'Clean callback with key: {key}')
    async def handle_other_paths(self, websocket, path):
        timeouts = 0
        key = None
        user_key = None
        try:
            while True:
                try:
                    start_wait_recv = time.time()
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    delay = (time.time() - start_wait_recv) * 1000

                    start_json = time.time()
                    # Parse JSON directly without thread pool
                    message = json.loads(message)
                    json_delay = (time.time() - start_json) * 1000
                    user_key = user_id_default
                    if 'session_id' in message and self.tokens_store:
                        message['session_state'] = self.tokens_store.get_session_state(message['session_id'])
                    if 'user_id' in message:
                        if self.tokens_store:
                            message['user_state'] = self.tokens_store.get_user_state(message['user_id'])
                        user_key = message['user_id']
                    key = message['id']


                    if not user_key:
                        user_key = user_id_default
                    (self.logger.info if delay < 20 else self.logger.warning)(
                        f"Socket await for key {key} recv_delay {delay} ms, json_delay: {json_delay} ms")

                    websocket.is_component_ready = True
                    self.logger.info(f'Got callback with key: {key}')

                    def send_login_error(id):
                        self.send_data(
                            {'id': id, 'event': 'message', 'data': {'message': error_auth_text, 'type': 'error'}})

                    if user_key in self.callbacks:
                        if key in self.callbacks[user_key]:
                            if self.tokens_store:
                                if 'accessToken' in message:
                                    accessToken = message['accessToken']
                                    if self.tokens_store.check_valid(accessToken):
                                        # Extract callback data - handle both 2-tuple and 3-tuple format
                                        callback_data = self.callbacks[user_key][key]
                                        if len(callback_data) == 2:
                                            callback, submit_time = callback_data
                                            timeout = None
                                        else:
                                            callback, submit_time, timeout = callback_data
                                        
                                        delay = (time.time() - submit_time) * 1000
                                        (self.logger.info if delay < 20 else self.logger.warning)(
                                            f'Calling key: {key}, user: {user_key}, for {callback}, delay: {delay}ms, timeout: {timeout}s')
                                        
                                        try:
                                            await self._execute_callback_with_timeout(callback, message, timeout)
                                        except asyncio.TimeoutError:
                                            # Send timeout error to client
                                            self.send_data({
                                                'id': key,
                                                'event': 'error',
                                                'data': {
                                                    'message': f'Operation timed out after {timeout} seconds',
                                                    'type': 'timeout',
                                                    'timeout': timeout
                                                }
                                            })
                                    else:
                                        send_login_error(key)
                                else:
                                    send_login_error(key)
                            else:
                                # Extract callback data - handle both 2-tuple and 3-tuple format
                                callback_data = self.callbacks[user_key][key]
                                if len(callback_data) == 2:
                                    callback, submit_time = callback_data
                                    timeout = None
                                else:
                                    callback, submit_time, timeout = callback_data
                                
                                delay = (time.time() - submit_time) * 1000
                                (self.logger.info if delay < 20 else self.logger.warning)(
                                    f'Calling key: {key}, for {callback}, delay: {delay}ms, timeout: {timeout}s')
                                
                                try:
                                    await self._execute_callback_with_timeout(callback, message, timeout)
                                except asyncio.TimeoutError:
                                    # Send timeout error to client
                                    self.send_data({
                                        'id': key,
                                        'event': 'error',
                                        'data': {
                                            'message': f'Operation timed out after {timeout} seconds',
                                            'type': 'timeout',
                                            'timeout': timeout
                                        }
                                    })


                except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
                    self.logger.warning('Error in communicating with socket')
                    break
                except asyncio.TimeoutError:
                    self.logger.debug('Asyncio timeout')
                    if not websocket.open:
                        self.logger.warning('Closing socket - Asyncio timeout')
                        break
                except Exception as exc:
                    self.logger.exception(f'Error in socket handler: {exc}')
                    # Send error response using the key that was being processed
                    if 'key' in locals() and key:
                        try:
                            self.send_data({'id': key, 'event': 'message',
                                          'data': {'message': f'Error in socket handler: {exc}', 'type': 'error',
                                                   'open': True}})
                        except Exception as send_error:
                            self.logger.exception(f'Failed to send error response: {send_error}')
        finally:
            if path is not None and path in self.clients:
                self.logger.info(f'Popping from clients: {path}')
                self.clients.pop(path)
                if 'user_key' in locals() and user_key:
                    self.removeByKeyFragment(path, user_key)

    async def client_for_key(self, key, timeout):
        start_time = time.time()
        while True:
            client = self.clients.get(key, None)
            if client is not None and client.is_component_ready:
                return client
            elif time.time() - start_time > timeout:
                break
            await asyncio.sleep(0.1)  # Sleep for a small interval to avoid busy-waiting
        return None

    def _send_data_async(self, data, calltime):
        try:
            call_delay = (time.time() - calltime) * 1000

            (self.logger.debug if call_delay < 2 else self.logger.warning)(
                f'_send_data_async call delay is {call_delay} ms')
            start = time.time()
            data_as_json_string = json.dumps(data, cls=CustomJSONEncoder)
            json_delay = (time.time() - start) * 1000
            (self.logger.debug if json_delay < 2 else self.logger.warning)(
                f'_send_data_async json dumps took delay is {json_delay} ms')

            if os.name == 'nt':
                key = f"/ws/{data['id']}"
            else:
                key = os.path.join("/ws", data['id'])

            start = time.time()
            client = asyncio.run(self.client_for_key(key, self.timeout))
            client_for_key_delay = (time.time() - start) * 1000
            (self.logger.debug if client_for_key_delay < 0.5 else self.logger.warning)(
                f'_send_data_async client_for_key took delay is {client_for_key_delay} ms')

            if client and client.open:
                start = time.time()
                asyncio.run(client.send(data_as_json_string))
                data_as_json_string_delay = (time.time() - start) * 1000
                (self.logger.info if data_as_json_string_delay < 20 else self.logger.warning)(
                    f'_send_data_async data_as_json_string_delay took delay is {data_as_json_string_delay} ms, data length: {len(data_as_json_string)}')

                # await asyncio.wait_for(, timeout=self.timeout)
                self.logger.info(f'Sent for {key}')
            else:
                if client is None:
                    self.logger.warn(f'No client for key: {key}')
                else:
                    self.logger.warn(f'Client for key: {key} is no longer open')
        except Exception as exc:
            self.logger.exception('Error')

    async def _send_data_coroutine(self, data, calltime):
        """Async version of send_data without asyncio.run()"""
        try:
            call_delay = (time.time() - calltime) * 1000

            (self.logger.debug if call_delay < 2 else self.logger.warning)(
                f'_send_data_coroutine call delay is {call_delay} ms')
            start = time.time()
            data_as_json_string = json.dumps(data, cls=CustomJSONEncoder)
            json_delay = (time.time() - start) * 1000
            (self.logger.debug if json_delay < 2 else self.logger.warning)(
                f'_send_data_coroutine json dumps took delay is {json_delay} ms')

            if os.name == 'nt':
                key = f"/ws/{data['id']}"
            else:
                key = os.path.join("/ws", data['id'])

            start = time.time()
            client = await self.client_for_key(key, self.timeout)  # Changed to await
            client_for_key_delay = (time.time() - start) * 1000
            (self.logger.debug if client_for_key_delay < 0.5 else self.logger.warning)(
                f'_send_data_coroutine client_for_key took delay is {client_for_key_delay} ms')

            if client and client.open:
                start = time.time()
                await client.send(data_as_json_string)  # Changed to await
                data_as_json_string_delay = (time.time() - start) * 1000
                (self.logger.info if data_as_json_string_delay < 20 else self.logger.warning)(
                    f'_send_data_coroutine data_as_json_string_delay took delay is {data_as_json_string_delay} ms, data length: {len(data_as_json_string)}')

                self.logger.info(f'Sent for {key}')
            else:
                if client is None:
                    self.logger.warn(f'No client for key: {key}')
                else:
                    self.logger.warn(f'Client for key: {key} is no longer open')
        except Exception as exc:
            self.logger.exception('Error in _send_data_coroutine')

    def send_data(self, data):  # Regular method
        calltime = time.time()
        
        if self.loop and self.loop.is_running():
            # Use the server's event loop
            asyncio.run_coroutine_threadsafe(
                self._send_data_coroutine(data, calltime),
                self.loop
            )
        else:
            # Fallback - just log and skip
            self.logger.warning("Cannot send data - server loop not running")

    async def _start_server_async(self):
        server = await websockets.serve(self.handler, self.host, self.port, ping_interval=5, ping_timeout=self.timeout)
        self.running_server = server
        self.logger.info(f"WebSocket server started at wss://{self.host}:{self.port}")
        await server.wait_closed()

    def start_server(self):  # Regular method
        self.logger.info("STARTING SERVER!!")

        def run():
            loop = asyncio.new_event_loop()
            self.loop = loop
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._start_server_async())

        if not self.is_running:
            self.server_thread = threading.Thread(target=run)
            self.server_thread.start()

    def execute_function_and_send_result(self, callback_function, *args, **kwargs):
        if callback_function:
            def wrapper():
                try:
                    data = callback_function(*args, **kwargs)
                    # Use send_data instead of _send_data_async
                    if data is not None:
                        self.send_data(data)
                except Exception as exc:
                    self.logger.exception('Error in calling callback')

            self.thread_pool_executor.submit(wrapper)

    def start_callbacks_by_key(self, key, session_id, user_id=user_id_default):
        try:
            if user_id and user_id in self.callbacks:
                user_callbacks = self.callbacks[user_id]
                message = {
                    'user_state': self.tokens_store.get_user_state(user_id) if self.tokens_store else None,
                    'session_state': self.tokens_store.get_session_state(session_id) if self.tokens_store else None,
                }
                count = 0
                for callback_key, callback_data in user_callbacks.items():
                    if key in callback_key:
                        # Handle both 2-tuple and 3-tuple format
                        if len(callback_data) == 2:
                            callback_function, timestamp = callback_data
                        else:
                            callback_function, timestamp, timeout = callback_data
                        self.execute_function_and_send_result(callback_function, message)
                        count += 1
                self.logger.info(f"Total callbacks executed: {count}")
        except Exception as exc:
            self.logger.info(f'Error in calling  start_callbacks_by_key')

    def register_callback(self, id, callback_function, user_id=user_id_default, timeout=None):
        """
        Register a callback function with optional timeout.
        
        Args:
            id: Component identifier
            callback_function: Function to call when message received
            user_id: User identifier (default: 'user_id_default')
            timeout: Optional timeout in seconds. If None, uses SEEDOO_DEFAULT_CALLBACK_TIMEOUT
        """
        if timeout is None:
            timeout = self.default_callback_timeout
        
        self.logger.info(f'Registered callback: {safe_name(callback_function)} (timeout: {timeout}s)')
        if callback_function is not None:
            if user_id in self.callbacks:
                self.callbacks[user_id][id] = (callback_function, time.time(), timeout)
            else:
                self.callbacks[user_id] = {}
                self.callbacks[user_id][id] = (callback_function, time.time(), timeout)

    def register_function(self, target_function):
        func_name = safe_name(target_function)
        self.logger.info(f'Registered function: {func_name}')
        self.paths[func_name] = target_function
    
    def get_queue_stats(self):
        """Get statistics about queue performance"""
        if hasattr(self.thread_pool_executor, 'get_stats'):
            return self.thread_pool_executor.get_stats()
        else:
            # Basic stats for standard executor
            return {
                'active_threads': len(self.thread_pool_executor._threads),
                'queue_size': self.thread_pool_executor._work_queue.qsize() if hasattr(self.thread_pool_executor._work_queue, 'qsize') else 'unknown'
            }
    
    def get_timeout_stats(self):
        """Get timeout statistics"""
        if hasattr(self.thread_pool_executor, '_thread_timeout_stats'):
            return self.thread_pool_executor._thread_timeout_stats.copy()
        return None

    def __del__(self):
        # Close client websockets
        for _, websocket in self.clients.items():
            if not websocket.closed:
                asyncio.run(websocket.close())

        # Shut down the threatd pool executor
        self.thread_pool_executor.shutdown(wait=True)

        if self.running_server:
            self.running_server.close()

        # If your websocket server implementation allows for graceful shutdown,
        # you can also attempt to stop the server thread here.
        # But you'd need to modify how you start and run the server for that.

        # For now, just log a message
        self.logger.info("WebSocketServer instance is being destroyed")


import atexit


def cleanup():
    # Call the C function to destroy the lock
    del WebSocketServer._instance


# Register the cleanup function
atexit.register(cleanup)
