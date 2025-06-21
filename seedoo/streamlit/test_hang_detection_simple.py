#!/usr/bin/env python3
"""
Simplified test to detect WebSocket server hanging issues.
Focuses on the core problem: asyncio.run() being called within callbacks.
"""

import asyncio
import websockets
import json
import threading
import time
import sys
import os
import logging
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_server import WebSocketServer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleHangTest:
    def __init__(self):
        self.server = None
        self.hang_detected = False
        self.asyncio_error_detected = False
        
    def test_asyncio_run_in_callback(self):
        """Test if callbacks can call asyncio.run() without error"""
        logger.info("Testing asyncio.run() in callback context...")
        
        def problematic_callback(message):
            """This callback tries to use asyncio.run() which will fail"""
            try:
                # This is what send_data() does internally
                asyncio.run(asyncio.sleep(0))
                return "Success"
            except RuntimeError as e:
                if "asyncio.run() cannot be called from a running event loop" in str(e):
                    logger.error("✗ DETECTED: asyncio.run() error in callback!")
                    self.asyncio_error_detected = True
                    raise
                    
        # Test in thread pool (simulating server behavior)
        executor = ThreadPoolExecutor(max_workers=1)
        
        try:
            # Submit callback to thread pool
            future = executor.submit(problematic_callback, {"test": "data"})
            result = future.result(timeout=5)
            logger.info("✓ asyncio.run() succeeded in thread pool")
        except RuntimeError as e:
            logger.error(f"✗ asyncio.run() failed: {e}")
            self.asyncio_error_detected = True
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            executor.shutdown()
            
        return self.asyncio_error_detected
        
    async def test_server_with_blocking_callback(self):
        """Test server behavior with callbacks that use send_data()"""
        logger.info("Testing server with blocking callbacks...")
        
        # Start server
        self.server = WebSocketServer("localhost", 9898)
        server_thread = threading.Thread(target=self.server.start_server, daemon=True)
        server_thread.start()
        await asyncio.sleep(2)  # Let server start
        
        # Track callback execution
        callback_executed = False
        callback_error = None
        
        def blocking_callback(message):
            """Callback that uses send_data (which calls asyncio.run)"""
            nonlocal callback_executed, callback_error
            try:
                logger.info("Callback executing...")
                # This will try to use asyncio.run() internally - must include 'id'
                self.server.send_data({
                    "id": "test_callback",  # Required for routing
                    "test": "data", 
                    "large": "x" * 10000
                })
                callback_executed = True
                logger.info("Callback completed successfully")
            except Exception as e:
                callback_error = e
                logger.error(f"Callback error: {e}")
                if "asyncio.run()" in str(e):
                    self.hang_detected = True
                    
        # Register callback
        self.server.register_callback("test_callback", blocking_callback, "test_user")
        
        # Trigger callback
        logger.info("Triggering callback...")
        try:
            self.server.start_callbacks_by_key("test_callback", "session_123", "test_user")
            
            # Wait for callback to complete
            await asyncio.sleep(3)
            
            if callback_error:
                logger.error(f"Callback failed with: {callback_error}")
            elif callback_executed:
                logger.info("Callback executed without hanging")
            else:
                logger.warning("Callback did not execute")
                
        except Exception as e:
            logger.error(f"Error triggering callback: {e}")
            
        return self.hang_detected
        
    async def test_concurrent_callbacks(self):
        """Test multiple callbacks executing concurrently"""
        logger.info("Testing concurrent callback execution...")
        
        callback_count = 10
        executed = []
        errors = []
        
        def create_callback(idx):
            def callback(message):
                try:
                    logger.info(f"Callback {idx} starting...")
                    # Simulate work
                    time.sleep(0.1)
                    # Try to send data (uses asyncio.run) - must include 'id'
                    self.server.send_data({
                        "id": f"callback_{idx}",  # Required for routing
                        "callback": idx, 
                        "data": "test"
                    })
                    executed.append(idx)
                    logger.info(f"Callback {idx} completed")
                except Exception as e:
                    errors.append((idx, e))
                    logger.error(f"Callback {idx} error: {e}")
            return callback
            
        # Register multiple callbacks
        for i in range(callback_count):
            self.server.register_callback(f"callback_{i}", create_callback(i), "test_user")
            
        # Trigger all callbacks concurrently
        logger.info(f"Triggering {callback_count} callbacks concurrently...")
        start_time = time.time()
        
        for i in range(callback_count):
            self.server.start_callbacks_by_key(f"callback_{i}", f"session_{i}", "test_user")
            
        # Wait for completion
        await asyncio.sleep(5)
        
        duration = time.time() - start_time
        logger.info(f"Execution took {duration:.2f}s")
        logger.info(f"Executed: {len(executed)}/{callback_count}")
        logger.info(f"Errors: {len(errors)}")
        
        if errors:
            for idx, error in errors[:3]:  # Show first 3 errors
                logger.error(f"  Callback {idx}: {error}")
                
        # Check if thread pool is exhausted
        if len(executed) < callback_count / 2:
            logger.critical("HANG DETECTED: Less than half of callbacks completed!")
            self.hang_detected = True
            
        return self.hang_detected


async def main():
    """Run the simplified hang detection tests"""
    test = SimpleHangTest()
    
    logger.info("=" * 60)
    logger.info("WebSocket Server Hang Detection Test")
    logger.info("=" * 60)
    
    # Test 1: Direct asyncio.run() test
    logger.info("\nTest 1: Testing asyncio.run() in thread pool")
    asyncio_issue = test.test_asyncio_run_in_callback()
    
    # Test 2: Server callback test
    logger.info("\nTest 2: Testing server with blocking callbacks")
    server_hang = await test.test_server_with_blocking_callback()
    
    # Test 3: Concurrent callbacks
    logger.info("\nTest 3: Testing concurrent callback execution")
    concurrent_hang = await test.test_concurrent_callbacks()
    
    # Results
    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS")
    logger.info("=" * 60)
    
    issues_found = []
    
    if asyncio_issue:
        issues_found.append("asyncio.run() cannot be called in callbacks")
        
    if server_hang:
        issues_found.append("Server callbacks hang when using send_data()")
        
    if concurrent_hang:
        issues_found.append("Thread pool exhaustion under concurrent load")
        
    if issues_found:
        logger.critical(f"\n❌ FAIL: {len(issues_found)} issue(s) detected:")
        for issue in issues_found:
            logger.critical(f"  - {issue}")
        logger.critical("\nThe server is vulnerable to hanging!")
        return 1
    else:
        logger.info("\n✅ PASS: No hanging issues detected")
        return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted")
        exit_code = 2
    sys.exit(exit_code)