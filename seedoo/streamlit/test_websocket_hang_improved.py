#!/usr/bin/env python3
"""
Improved unit test to reproduce and detect WebSocket server hanging issues.

This test implements proper isolation and monitoring strategies to reliably
detect hang conditions without being affected by them.
"""

import asyncio
import websockets
import json
import threading
import time
import sys
import os
import signal
import psutil
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import queue

# Add parent directory to path to import event_server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_server import WebSocketServer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IsolatedMonitor:
    """Base class for monitors that run in complete isolation"""
    
    def __init__(self, name: str):
        self.name = name
        self.hang_detected = False
        self._stop_event = threading.Event()
        
    def stop(self):
        """Signal the monitor to stop"""
        self._stop_event.set()
        
    def is_stopped(self):
        """Check if monitor should stop"""
        return self._stop_event.is_set()


class ProcessMonitor(IsolatedMonitor):
    """Monitor server process metrics from outside"""
    
    def __init__(self, server_pid: Optional[int] = None):
        super().__init__("ProcessMonitor")
        self.server_pid = server_pid or os.getpid()
        self.process = psutil.Process(self.server_pid)
        
    def run(self):
        """Monitor CPU and memory patterns"""
        cpu_samples = []
        stuck_counter = 0
        high_cpu_counter = 0
        
        while not self.is_stopped():
            try:
                # Sample CPU over 1 second
                cpu_percent = self.process.cpu_percent(interval=1)
                cpu_samples.append(cpu_percent)
                
                # Keep last 10 samples
                if len(cpu_samples) > 10:
                    cpu_samples.pop(0)
                
                # Memory usage
                memory_mb = self.process.memory_info().rss / 1024 / 1024
                
                # Detect stuck (very low CPU for extended period)
                if cpu_percent < 1:
                    stuck_counter += 1
                    if stuck_counter > 5:
                        logger.critical(f"HANG DETECTED: Process stuck (CPU: {cpu_percent}%)")
                        self.hang_detected = True
                        return
                else:
                    stuck_counter = 0
                
                # Detect spinning (very high CPU)
                if cpu_percent > 95:
                    high_cpu_counter += 1
                    if high_cpu_counter > 3:
                        logger.critical(f"HANG DETECTED: Process spinning (CPU: {cpu_percent}%)")
                        self.hang_detected = True
                        return
                else:
                    high_cpu_counter = 0
                
                logger.debug(f"Process metrics - CPU: {cpu_percent:.1f}%, Memory: {memory_mb:.1f}MB")
                
            except Exception as e:
                logger.error(f"Process monitor error: {e}")
                
            time.sleep(1)


class ExternalHealthCheck(IsolatedMonitor):
    """Health check that runs in a separate process"""
    
    def __init__(self, port: int, result_queue: multiprocessing.Queue):
        super().__init__("ExternalHealthCheck")
        self.port = port
        self.result_queue = result_queue
        self.loop = None
        
    async def _check_health(self):
        """Perform end-to-end health check"""
        consecutive_failures = 0
        max_failures = 3
        
        while not self.is_stopped():
            try:
                start = time.time()
                uri = f"ws://localhost:{self.port}/ws/health_external"
                
                # Full end-to-end test with callback
                async with asyncio.timeout(5):
                    async with websockets.connect(uri) as ws:
                        # Register a test callback
                        await ws.send(json.dumps({
                            "id": "health_check",
                            "user_id": "health_monitor",
                            "action": "register_callback",
                            "callback_id": f"health_{int(time.time())}"
                        }))
                        
                        # Trigger the callback
                        await ws.send(json.dumps({
                            "action": "trigger_callback",
                            "callback_id": f"health_{int(time.time())}"
                        }))
                        
                        # Wait for callback response
                        response = await ws.recv()
                        data = json.loads(response)
                        
                        if data.get("callback_executed"):
                            duration = time.time() - start
                            if duration > 3:
                                logger.warning(f"Health check slow: {duration:.2f}s")
                            consecutive_failures = 0
                        else:
                            consecutive_failures += 1
                            
            except asyncio.TimeoutError:
                consecutive_failures += 1
                logger.error(f"Health check timeout! ({consecutive_failures}/{max_failures})")
                if consecutive_failures >= max_failures:
                    logger.critical("HANG DETECTED: External health check failed!")
                    self.hang_detected = True
                    self.result_queue.put(True)
                    return
                    
            except Exception as e:
                logger.error(f"External health check error: {e}")
                consecutive_failures += 1
                
            await asyncio.sleep(1)
            
        self.result_queue.put(False)
        
    def run(self):
        """Run health check in new event loop"""
        # Create completely separate event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._check_health())
        finally:
            self.loop.close()


class ThreadPoolMonitor(IsolatedMonitor):
    """Monitor thread pool using separate resources"""
    
    def __init__(self, target_executor: ThreadPoolExecutor):
        super().__init__("ThreadPoolMonitor")
        self.target_executor = target_executor
        # Create our own executor for testing
        self.test_executor = ThreadPoolExecutor(max_workers=1)
        
    def run(self):
        """Monitor thread pool health"""
        consecutive_blocks = 0
        max_blocks = 3
        
        while not self.is_stopped():
            try:
                # Count threads from target executor
                target_threads = [t for t in threading.enumerate() 
                                if hasattr(t, 'name') and 'ThreadPoolExecutor' in t.name]
                
                # Test if we can schedule work (using OUR executor to test)
                def test_target_executor():
                    # Try to submit to target executor with timeout
                    try:
                        future = self.target_executor.submit(lambda: "test")
                        return future.result(timeout=2)
                    except Exception:
                        return None
                
                # Run test in our executor
                test_future = self.test_executor.submit(test_target_executor)
                result = test_future.result(timeout=3)
                
                if result is None:
                    consecutive_blocks += 1
                    logger.error(f"Thread pool blocked! ({consecutive_blocks}/{max_blocks})")
                    logger.error(f"Target threads: {len(target_threads)}")
                    
                    if consecutive_blocks >= max_blocks:
                        logger.critical("HANG DETECTED: Thread pool exhausted!")
                        self.hang_detected = True
                        return
                else:
                    consecutive_blocks = 0
                    
            except Exception as e:
                logger.error(f"Thread pool monitor error: {e}")
                consecutive_blocks += 1
                
            time.sleep(1)
            
    def cleanup(self):
        """Clean up our test executor"""
        self.test_executor.shutdown(wait=False)


class CallbackTracker:
    """Track callback execution times"""
    
    def __init__(self):
        self.active_callbacks: Dict[str, float] = {}
        self.lock = threading.Lock()
        
    def start_callback(self, callback_id: str):
        """Mark callback as started"""
        with self.lock:
            self.active_callbacks[callback_id] = time.time()
            
    def end_callback(self, callback_id: str):
        """Mark callback as completed"""
        with self.lock:
            self.active_callbacks.pop(callback_id, None)
            
    def get_stuck_callbacks(self, timeout: float = 10) -> List[str]:
        """Get list of callbacks that have been running too long"""
        current_time = time.time()
        stuck = []
        
        with self.lock:
            for callback_id, start_time in self.active_callbacks.items():
                if current_time - start_time > timeout:
                    stuck.append((callback_id, current_time - start_time))
                    
        return stuck


class ImprovedWebSocketServerHangTest:
    """Improved test suite with proper isolation and monitoring"""
    
    def __init__(self):
        self.server: Optional[WebSocketServer] = None
        self.hang_detected = False
        self.test_timeout = 30
        self.server_port = 9898
        self.monitors: List[IsolatedMonitor] = []
        self.callback_tracker = CallbackTracker()
        self.external_process = None
        
    def create_wrapped_callback(self, callback_id: str, original_callback):
        """Wrap callbacks to track execution time"""
        def wrapped(message):
            self.callback_tracker.start_callback(callback_id)
            try:
                return original_callback(message)
            finally:
                self.callback_tracker.end_callback(callback_id)
        return wrapped
        
    def flood_with_callbacks(self, num_callbacks: int = 100):
        """Register callbacks with tracking"""
        def create_callback(callback_id: int):
            def callback(message: Dict[str, Any]):
                # Large payload
                large_data = {
                    "id": f"callback_{callback_id}",
                    "data": {
                        "items": [{"x": i, "data": "x" * 100} for i in range(5000)]
                    },
                    "timestamp": time.time()
                }
                
                try:
                    self.server.send_data(large_data)
                except RuntimeError as e:
                    if "asyncio.run()" in str(e):
                        logger.error(f"Callback {callback_id} hit asyncio.run() error!")
                        self.hang_detected = True
                        
            return callback
        
        # Register wrapped callbacks
        for i in range(num_callbacks):
            callback_id = f"test_callback_{i}"
            wrapped = self.create_wrapped_callback(
                callback_id,
                create_callback(i)
            )
            self.server.register_callback(callback_id, wrapped, "test_user")
            
    def start_external_health_check(self):
        """Start health check in separate process"""
        result_queue = multiprocessing.Queue()
        
        def run_external_check():
            monitor = ExternalHealthCheck(self.server_port, result_queue)
            monitor.run()
            
        self.external_process = multiprocessing.Process(
            target=run_external_check,
            daemon=True
        )
        self.external_process.start()
        
        # Check results periodically
        def check_results():
            while not self.hang_detected:
                try:
                    if result_queue.get(timeout=1):
                        self.hang_detected = True
                        return
                except:
                    pass
                    
        threading.Thread(target=check_results, daemon=True).start()
        
    async def run_hang_test(self):
        """Run improved hang detection test"""
        logger.info("Starting improved WebSocket server hang test...")
        
        # Start server
        self.server = WebSocketServer("localhost", self.server_port)
        server_thread = threading.Thread(target=self.server.start_server, daemon=True)
        server_thread.start()
        await asyncio.sleep(2)
        
        # Start monitors with proper isolation
        
        # 1. Process monitor
        process_monitor = ProcessMonitor()
        process_thread = threading.Thread(target=process_monitor.run, daemon=True)
        process_thread.start()
        self.monitors.append(process_monitor)
        
        # 2. Thread pool monitor with separate executor
        thread_monitor = ThreadPoolMonitor(self.server.thread_pool_executor)
        thread_thread = threading.Thread(target=thread_monitor.run, daemon=True)
        thread_thread.start()
        self.monitors.append(thread_monitor)
        
        # 3. External health check in separate process
        self.start_external_health_check()
        
        # 4. Callback tracking monitor
        def monitor_callbacks():
            while not self.hang_detected:
                stuck = self.callback_tracker.get_stuck_callbacks()
                if stuck:
                    for callback_id, duration in stuck:
                        logger.critical(f"HANG DETECTED: Callback {callback_id} stuck for {duration:.1f}s")
                    self.hang_detected = True
                    return
                time.sleep(1)
                
        callback_thread = threading.Thread(target=monitor_callbacks, daemon=True)
        callback_thread.start()
        
        # Create load
        logger.info("Creating slow clients and callbacks...")
        
        # Slow clients
        client_tasks = []
        for i in range(10):
            async def create_slow_client(client_id):
                uri = f"ws://localhost:{self.server_port}/ws/test_{client_id}"
                try:
                    async with websockets.connect(uri) as ws:
                        await ws.send(json.dumps({
                            "id": f"test_{client_id}",
                            "user_id": "test_user"
                        }))
                        while not self.hang_detected:
                            await asyncio.sleep(5)
                            try:
                                await asyncio.wait_for(ws.recv(), timeout=1)
                            except:
                                pass
                except Exception as e:
                    logger.debug(f"Client {client_id} error: {e}")
                    
            client_tasks.append(asyncio.create_task(create_slow_client(i)))
            
        # Register callbacks
        self.flood_with_callbacks(50)
        await asyncio.sleep(1)
        
        # Trigger callbacks
        logger.info("Triggering callbacks...")
        for i in range(50):
            self.server.start_callbacks_by_key(
                f"test_callback_{i}",
                f"session_{i}",
                "test_user"
            )
            
        # Monitor for hangs
        start_time = time.time()
        while not self.hang_detected and (time.time() - start_time) < self.test_timeout:
            # Check all monitors
            for monitor in self.monitors:
                if monitor.hang_detected:
                    self.hang_detected = True
                    break
            await asyncio.sleep(1)
            
        # Cleanup
        for task in client_tasks:
            task.cancel()
            
        for monitor in self.monitors:
            monitor.stop()
            
        if hasattr(thread_monitor, 'cleanup'):
            thread_monitor.cleanup()
            
        if self.external_process:
            self.external_process.terminate()
            
        return self.hang_detected


async def main():
    """Run the improved hang detection test"""
    test = ImprovedWebSocketServerHangTest()
    
    try:
        hang_detected = await test.run_hang_test()
        
        if hang_detected:
            logger.critical("\n❌ FAIL: Server hang detected!")
            return 1
        else:
            logger.info("\n✅ PASS: Server handled load without hanging")
            return 0
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return 3
    finally:
        if test.server:
            test.server.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)