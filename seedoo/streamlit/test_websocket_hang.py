#!/usr/bin/env python3
"""
Unit test to reproduce and detect WebSocket server hanging issues.

This test simulates the conditions that cause the WebSocket server to hang:
1. Thread pool exhaustion from concurrent callback executions
2. Slow WebSocket clients blocking send operations
3. Event loop conflicts from nested asyncio.run() calls
"""

import asyncio
import websockets
import json
import threading
import time
import sys
import os
import signal
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Optional, Dict, Any
import logging

# Add parent directory to path to import event_server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_server import WebSocketServer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WebSocketServerHangTest:
    """Test suite to detect WebSocket server hanging issues"""
    
    def __init__(self):
        self.server: Optional[WebSocketServer] = None
        self.hang_detected = False
        self.test_timeout = 30  # seconds
        self.health_check_timeout = 5  # seconds
        self.server_port = 9898
        self.monitoring_tasks = []
        
    async def create_slow_client(self, client_id: str, delay_recv: bool = True):
        """Create a WebSocket client that's slow to receive messages"""
        uri = f"ws://localhost:{self.server_port}/ws/test_{client_id}"
        try:
            async with websockets.connect(uri) as websocket:
                # Send initial registration message
                await websocket.send(json.dumps({
                    "id": f"test_{client_id}",
                    "user_id": "test_user"
                }))
                
                if delay_recv:
                    # Simulate slow client by delaying message processing
                    while not self.hang_detected:
                        await asyncio.sleep(5)  # Slow to process messages
                        try:
                            msg = await asyncio.wait_for(websocket.recv(), timeout=1)
                            logger.debug(f"Client {client_id} received: {len(msg)} bytes")
                        except asyncio.TimeoutError:
                            continue
                        except Exception:
                            break
        except Exception as e:
            logger.error(f"Client {client_id} error: {e}")
            
    def flood_with_callbacks(self, num_callbacks: int = 100):
        """Register many callbacks that all try to send data simultaneously"""
        def create_callback(callback_id: int):
            def callback(message: Dict[str, Any]):
                # Create large payload to slow JSON serialization
                large_data = {
                    "id": f"callback_{callback_id}",
                    "data": {
                        "items": [{"x": i, "data": "x" * 100} for i in range(5000)],
                        "nested": {
                            "level1": {
                                "level2": [{"item": j} for j in range(1000)]
                            }
                        }
                    },
                    "timestamp": time.time()
                }
                
                # This is where the hang occurs - send_data uses asyncio.run()
                # which can't be called when an event loop is already running
                try:
                    self.server.send_data(large_data)
                except RuntimeError as e:
                    if "asyncio.run()" in str(e):
                        logger.error(f"Callback {callback_id} hit asyncio.run() error!")
                        self.hang_detected = True
                        
            return callback
        
        # Register callbacks
        for i in range(num_callbacks):
            self.server.register_callback(
                f"test_callback_{i}",
                create_callback(i),
                "test_user"
            )
            
    async def health_check(self):
        """Continuously check if server is responsive"""
        consecutive_failures = 0
        max_failures = 3
        
        while not self.hang_detected:
            try:
                start = time.time()
                uri = f"ws://localhost:{self.server_port}/ws/health"
                
                # Try to connect and get response within timeout
                async with asyncio.timeout(self.health_check_timeout):
                    async with websockets.connect(uri) as ws:
                        await ws.send(json.dumps({
                            "id": "health_check",
                            "user_id": "health_monitor",
                            "ping": True
                        }))
                        response = await ws.recv()
                        
                duration = time.time() - start
                if duration > 3:
                    logger.warning(f"Health check slow: {duration:.2f}s")
                    
                consecutive_failures = 0
                
            except asyncio.TimeoutError:
                consecutive_failures += 1
                logger.error(f"Health check timeout! ({consecutive_failures}/{max_failures})")
                if consecutive_failures >= max_failures:
                    logger.critical("HANG DETECTED: Health check timeouts exceeded threshold!")
                    self.hang_detected = True
                    return False
                    
            except Exception as e:
                logger.error(f"Health check error: {e}")
                consecutive_failures += 1
                
            await asyncio.sleep(1)
            
        return not self.hang_detected
        
    def monitor_thread_pool(self):
        """Monitor thread pool for all threads being blocked"""
        if not self.server or not hasattr(self.server, 'thread_pool_executor'):
            logger.error("Server or thread pool not available")
            return
            
        executor = self.server.thread_pool_executor
        consecutive_blocks = 0
        max_blocks = 3
        
        while not self.hang_detected:
            try:
                # Get current thread count
                active_threads = len([t for t in threading.enumerate() 
                                    if t.name.startswith('ThreadPoolExecutor')])
                
                # Submit a simple task with timeout to test if pool is responsive
                future = executor.submit(lambda: "thread_pool_test")
                try:
                    result = future.result(timeout=2)
                    consecutive_blocks = 0
                except FutureTimeoutError:
                    consecutive_blocks += 1
                    logger.error(f"Thread pool blocked! ({consecutive_blocks}/{max_blocks})")
                    logger.error(f"Active threads: {active_threads}")
                    
                    if consecutive_blocks >= max_blocks:
                        logger.critical("HANG DETECTED: Thread pool exhausted!")
                        self.hang_detected = True
                        return False
                        
            except Exception as e:
                logger.error(f"Thread monitor error: {e}")
                
            time.sleep(1)
            
        return not self.hang_detected
        
    def monitor_callback_execution(self):
        """Monitor if callbacks are completing in reasonable time"""
        callback_timeouts = {}
        max_timeout = 10  # seconds
        
        while not self.hang_detected:
            # Track callback execution times
            current_time = time.time()
            
            # Check for stuck callbacks
            for callback_id, start_time in list(callback_timeouts.items()):
                if current_time - start_time > max_timeout:
                    logger.critical(f"HANG DETECTED: Callback {callback_id} stuck for {current_time - start_time:.1f}s")
                    self.hang_detected = True
                    return False
                    
            time.sleep(1)
            
        return not self.hang_detected
        
    async def test_asyncio_run_conflict(self):
        """Test for asyncio.run() being called within existing event loop"""
        try:
            # This simulates what happens in the callbacks
            def problematic_callback():
                # This will fail if called from within an async context
                asyncio.run(asyncio.sleep(0))
                
            # Try to execute in thread pool (mimics the server behavior)
            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(None, problematic_callback)
            
            try:
                await asyncio.wait_for(future, timeout=5)
            except RuntimeError as e:
                if "asyncio.run() cannot be called from a running event loop" in str(e):
                    logger.error("Detected asyncio.run() conflict!")
                    return True
                    
        except Exception as e:
            logger.error(f"asyncio.run test error: {e}")
            
        return False
        
    async def run_hang_test(self):
        """Main test orchestrator"""
        logger.info("Starting WebSocket server hang test...")
        
        # Start server
        self.server = WebSocketServer("localhost", self.server_port)
        server_thread = threading.Thread(target=self.server.start_server, daemon=True)
        server_thread.start()
        await asyncio.sleep(2)  # Let server start
        
        # Start monitoring tasks
        health_task = asyncio.create_task(self.health_check())
        
        thread_monitor = threading.Thread(target=self.monitor_thread_pool, daemon=True)
        thread_monitor.start()
        
        callback_monitor = threading.Thread(target=self.monitor_callback_execution, daemon=True)
        callback_monitor.start()
        
        # Test for asyncio.run() conflict
        logger.info("Testing for asyncio.run() conflicts...")
        has_asyncio_conflict = await self.test_asyncio_run_conflict()
        if has_asyncio_conflict:
            logger.warning("asyncio.run() conflict detected - this will cause hangs!")
        
        # Create slow clients
        logger.info("Creating slow WebSocket clients...")
        client_tasks = []
        for i in range(10):
            client_tasks.append(
                asyncio.create_task(self.create_slow_client(str(i)))
            )
            
        # Flood with callbacks
        logger.info("Registering flood of callbacks...")
        self.flood_with_callbacks(50)
        
        # Give callbacks time to register
        await asyncio.sleep(1)
        
        # Trigger all callbacks simultaneously
        logger.info("Triggering all callbacks simultaneously...")
        trigger_tasks = []
        for i in range(50):
            # Start callbacks from different async tasks to maximize concurrency
            async def trigger_callback(idx):
                self.server.start_callbacks_by_key(
                    f"test_callback_{idx}", 
                    f"session_{idx}", 
                    "test_user"
                )
            trigger_tasks.append(asyncio.create_task(trigger_callback(i)))
            
        # Wait for triggers to complete or timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*trigger_tasks, return_exceptions=True),
                timeout=5
            )
        except asyncio.TimeoutError:
            logger.warning("Callback triggers timed out")
            
        # Wait for hang detection or test timeout
        logger.info("Waiting for hang detection or timeout...")
        start_time = time.time()
        
        while not self.hang_detected and (time.time() - start_time) < self.test_timeout:
            await asyncio.sleep(1)
            
        # Cancel client tasks
        for task in client_tasks:
            task.cancel()
            
        # Final status
        return self.hang_detected


async def main():
    """Run the hang detection test"""
    test = WebSocketServerHangTest()
    
    try:
        hang_detected = await test.run_hang_test()
        
        if hang_detected:
            logger.critical("\n❌ FAIL: Server hang detected!")
            logger.critical("The WebSocket server is vulnerable to hanging under load.")
            logger.critical("Likely causes:")
            logger.critical("  1. Thread pool exhaustion from concurrent callbacks")
            logger.critical("  2. asyncio.run() being called within existing event loop")
            logger.critical("  3. Synchronous blocking in async context")
            return 1
        else:
            logger.info("\n✅ PASS: Server handled load without hanging")
            logger.info("The server remained responsive under stress conditions.")
            return 0
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 2
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return 3
    finally:
        # Cleanup
        if test.server:
            test.server.close()


if __name__ == "__main__":
    # Handle process termination gracefully
    def signal_handler(sig, frame):
        logger.info("Received termination signal, shutting down...")
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)