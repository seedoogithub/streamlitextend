import asyncio
import logging
import multiprocessing
import websockets
import websockets.exceptions
import threading
import msgpack
import json
from seedoo.streamlit.tracking_executor import TrackingThreadPoolExecutor, safe_name
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import time
import os
import functools
import weakref
from streamlit.runtime.scriptrunner import add_script_run_ctx
SEEDOO_SEMAPHORE_NAME = 'seedoo_ux_semaphore'

class WebSocketServer:
    _instance = None

    @classmethod
    def instance(cls):
        if WebSocketServer._instance is None:
            port = int(os.environ.get('SEEDOO_WEBSOCKET_EVENT_PORT', '9898'))
            forwarded_port = os.environ.get('SEEDOO_WEBSOCKET_EVENT_PORT_FORWARDED', '')
            host = os.environ.get('SEEDOO_WEBSOCKET_EVENT_HOST', 'localhost')
            if forwarded_port:
                port = int(forwarded_port)

            WebSocketServer._instance = WebSocketServer(host, port=port)
            WebSocketServer._instance.start_server()

        return WebSocketServer._instance

    def __init__(self, host="localhost", port=9897):
        self.host = host
        self.logger = logging.getLogger(__name__)
        self.port = port
        self.callbacks = {}
        self.timeout = 300
        self.paths = {}
        self.is_running = False
        self.initialized_contexts = False
        self.running_server = None
        num_cpus = multiprocessing.cpu_count()
        self.thread_pool_executor = TrackingThreadPoolExecutor(max_workers=80, timeout = 180)

        def empty():
            return

        for _ in range(20):
            self.thread_pool_executor.submit(empty)

        self.clients = {} # Keep track of connected clients

    async def handler(self, websocket, path):
        self.logger.info(f"CONNECTED {path}")
        if path in self.clients:
            self.logger.warn(f'Path {path} is already in clients!')
        self.clients[path] = websocket
        websocket.is_component_ready = False
        print(path)
        if path.startswith('/ws/functions') or path.startswith('/wss/functions'):
            while True:
                target_function_name = ''
                try:
                    target_function = os.path.basename(path)
                    target_function_name = target_function_name
                    message = await asyncio.wait_for(websocket.recv(), timeout=self.timeout)  # 10-second timeout
                    if target_function not in self.paths:
                        self.logger.critical(f'Target requested function: {target_function} is not registered.')
                    else:
                        try:
                            target_function = self.paths[target_function]
                            target_function_name = safe_name(target_function)
                            self.logger.info(f'Executing function: {target_function_name}')
                            start = time.time()
                            message_data = json.loads(message)
                            duration = (time.time() - start) * 1000
                            (self.logger.warning if duration > 50 else self.logger.debug)(f'message data json load: {duration} ms')

                            start = time.time()
                            response = target_function(message_data)
                            duration = (time.time() - start) * 1000
                            (self.logger.warning if duration > 500 else self.logger.debug)(f'function {target_function_name} executed for {duration} ms')

                            if message_data.get('binary'):
                                self.logger.info('Sending binary response')
                                binary_data = msgpack.packb(response, use_bin_type=True)
                                await websocket.send(binary_data)
                            else:
                                self.logger.info('Sending text json response')
                                await websocket.send(json.dumps(response))

                        except Exception as exc:
                            self.logger.exception(f'Error in calling target function: {target_function_name} on path {path}, message was: {message}')
                except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
                    self.logger.warning(f'Error in communicating with socket for function: {target_function_name}')
                    break
                except asyncio.TimeoutError as exc:
                    self.logger.warning('Asyncio timeout')
                    if not websocket.open:
                        self.logger.warning('Closing socket - Asyncio timeout')
                        break
                except Exception as exc:
                    self.logger.exception('Error in socket handler')
        else:
            timeouts = 0
            key = None
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=self.timeout)  # 10-second timeout
                        message = json.loads(message)
                        key = message['id']
                        websocket.is_component_ready = True

                        if key in self.callbacks:
                            self.thread_pool_executor.submit(self.callbacks[key], message)

                    except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
                        self.logger.warning('Error in communicating with socket')
                        break
                    except asyncio.TimeoutError as exc:
                        self.logger.warning('Asyncio timeout')
                        if not websocket.open:
                            self.logger.warning('Closing socket - Asyncio timeout')
                            break


                    except Exception as exc:
                        self.logger.exception('Error in socket handler')
            finally:
                if path is not None and path in self.clients:
                    self.logger.info(f'Popping from clients: {path}')
                    self.clients.pop(path)

    async def client_for_key(self, key, timeout):
        start_time = time.time()
        while True:
            client = self.clients.get(key, None)
            if client is not None and client.is_component_ready:
                return client
            elif time.time() - start_time > timeout:
                break
            await asyncio.sleep(0.15)  # Sleep for a small interval to avoid busy-waiting
        return None

    def _send_data_async(self, data):
        try:
            data_as_json_string = json.dumps(data)
            if os.name == 'nt':
                key = f"/ws/{data['id']}"
            else:
                key = os.path.join("/ws", data['id'])

            client = asyncio.run(self.client_for_key(key, self.timeout))

            if client and client.open:
                asyncio.run(client.send(data_as_json_string))
                #await asyncio.wait_for(, timeout=self.timeout)
                self.logger.info(f'Sent for {key}')
            else:
                if client is None:
                    self.logger.warn(f'No client for key: {key}')
                else:
                    self.logger.warn(f'Client for key: {key} is no longer open')
        except Exception as exc:
            self.logger.exception('Error')

    def send_data(self, data):  # Regular method
        self.thread_pool_executor.submit(self._send_data_async, data)

    async def _start_server_async(self):
        server = await websockets.serve(self.handler, self.host, self.port, ping_interval = 5, ping_timeout=self.timeout)
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

    def execute_function_and_send_result(self, callback_function,  *args, **kwargs):
        if callback_function:
            def wrapper():
                try:
                    data = callback_function(*args, **kwargs)
                    self.send_data(data)
                    #self._send_data_async(data, json.dumps(data))
                except Exception as exc:
                    self.logger.exception('Error in calling callback')

            self.thread_pool_executor.submit(wrapper)

    def register_callback(self, id, callback_function):
        self.logger.info(f'Registered callback: {safe_name(callback_function)}')
        if callback_function is not None:
            self.callbacks[id] = callback_function

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

