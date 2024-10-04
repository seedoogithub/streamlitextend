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
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

SEEDOO_SEMAPHORE_NAME = 'seedoo_ux_semaphore'
error_auth_text = 'user not authenticated'
user_id_default = 'user_id_default'


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.astype(int).tolist()
        return super(CustomJSONEncoder, self).default(obj)


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
        num_cpus = multiprocessing.cpu_count()
        self.thread_pool_executor = TrackingThreadPoolExecutor(max_workers=80, timeout=180)

        def empty():
            return

        for _ in range(80):
            self.thread_pool_executor.submit(empty)

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
            if 'session_id' in message_data:
                message_data['session_state'] = self.tokens_store.get_session_state(message_data['session_id'])
            if 'user_id' in message_data:
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
            text_response = await asyncio.get_running_loop().run_in_executor(self.thread_pool_executor, json.dumps,
                                                                             response)
            json_delay = (time.time() - start) * 1000
            (self.logger.debug if json_delay < 20 else self.logger.warning)(
                f'_send_data_async json dumps took delay is {json_delay} ms')

            await websocket.send(text_response)

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
                    message = await asyncio.get_running_loop().run_in_executor(self.thread_pool_executor, json.loads,
                                                                               message)
                    json_delay = (time.time() - start_json) * 1000
                    user_key = user_id_default
                    if 'session_id' in message:
                        message['session_state'] = self.tokens_store.get_session_state(message['session_id'])
                    if 'user_id' in message:
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
                                        callback, submit_time = self.callbacks[user_key][key]
                                        delay = (time.time() - submit_time) * 1000
                                        (self.logger.info if delay < 20 else self.logger.warning)(
                                            f'Calling key: {key},user: {user_key}, for {callback}, delay: {delay}')
                                        await asyncio.get_running_loop().run_in_executor(self.thread_pool_executor,
                                                                                         callback, message)
                                    else:
                                        send_login_error(key)
                                else:
                                    send_login_error(key)
                            else:
                                callback, submit_time = self.callbacks[user_key][key]
                                delay = (time.time() - submit_time) * 1000
                                (self.logger.info if delay < 20 else self.logger.warning)(
                                    f'Calling key: {key}, for {callback}, delay: {delay}')
                                await asyncio.get_running_loop().run_in_executor(self.thread_pool_executor,
                                                                                 callback, message)


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
        finally:
            if path is not None and path in self.clients:
                self.logger.info(f'Popping from clients: {path}')
                self.clients.pop(path)
                if user_key:
                    self.removeByKeyFragment(path,user_key)

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

    def send_data(self, data):  # Regular method
        calltime = time.time()
        self.thread_pool_executor.submit(self._send_data_async, data, calltime)

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
            calltime = time.time()

            def wrapper():
                try:
                    data = callback_function(*args, **kwargs)
                    self._send_data_async(data, calltime)
                except Exception as exc:
                    self.logger.exception('Error in calling callback')

            self.thread_pool_executor.submit(wrapper)

    def start_callbacks_by_key(self, key, session_id, user_id=user_id_default):
        try:
            if user_id and user_id in self.callbacks:
                user_callbacks = self.callbacks[user_id]
                message = {
                    'user_state': self.tokens_store.get_user_state(user_id),
                    'session_state': self.tokens_store.get_session_state(session_id),
                }
                count = 0
                for callback_key, (callback_function, timestamp) in user_callbacks.items():
                    if key in callback_key:
                        self.execute_function_and_send_result(callback_function, message )
                        count += 1
                self.logger.info(f"Total callbacks executed: {count}")
        except Exception as exc:
            self.logger.info(f'Error in calling  start_callbacks_by_key')

    def register_callback(self, id, callback_function, user_id=user_id_default):
        self.logger.info(f'Registered callback: {safe_name(callback_function)}')
        if callback_function is not None:
            if user_id in self.callbacks:
                self.callbacks[user_id][id] = (callback_function, time.time())
            else:
                self.callbacks[user_id] = {}
                self.callbacks[user_id][id] = (callback_function, time.time())

    def register_function(self, target_function):
        func_name = safe_name(target_function)
        self.logger.info(f'Registered function: {func_name}')
        self.paths[func_name] = target_function

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
