#!/usr/bin/env python3
"""
Comprehensive test suite for WebSocket event server functionality.
Tests all use cases with real WebSocket connections to ensure no regression.
"""

import unittest
import asyncio
import websockets
import json
import msgpack
import time
import threading
import sys
import os
from unittest.mock import Mock, MagicMock, patch
import numpy as np
from concurrent.futures import TimeoutError as FutureTimeoutError
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_server import WebSocketServer

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class WebSocketServerTestSuite(unittest.TestCase):
    """Comprehensive test suite for WebSocket server functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Start server once for all tests"""
        cls.test_port = 9899
        cls.server = WebSocketServer("localhost", cls.test_port)
        cls.server.start_server()
        time.sleep(2)  # Allow server to start
        
    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        # Note: WebSocketServer doesn't have a stop method, so we rely on process cleanup
        pass
        
    def setUp(self):
        """Reset state before each test"""
        self.server.callbacks.clear()
        self.server.paths.clear()
        if hasattr(self.server, 'tokens_store'):
            self.server.tokens_store = None
        self.received_messages = []
        self.test_passed = False
        
    def tearDown(self):
        """Cleanup after each test"""
        # Give time for connections to close
        time.sleep(0.1)

    # ========== Connection Management Tests ==========
    
    async def test_client_connection_tracking(self):
        """Test that clients are properly tracked and cleaned up"""
        initial_clients = len(self.server.clients)
        
        uri = f"ws://localhost:{self.test_port}/ws/test_client_1"
        
        # Connect
        async with websockets.connect(uri) as websocket:
            await asyncio.sleep(0.5)
            during_clients = len(self.server.clients)
            # Client should be tracked
            self.assertEqual(during_clients, initial_clients + 1)
            self.assertIn("/ws/test_client_1", self.server.clients)
            
            # Send registration message (just component ID)
            await websocket.send(json.dumps({
                "id": "test_client_1"
            }))
        
        # After disconnect
        await asyncio.sleep(0.5)
        final_clients = len(self.server.clients)
        # Client should be removed
        self.assertEqual(final_clients, initial_clients)
        self.assertNotIn("/ws/test_client_1", self.server.clients)

    async def test_multiple_concurrent_connections(self):
        """Test multiple clients can connect simultaneously"""
        initial_count = len(self.server.clients)
        clients = []
        num_clients = 5
        
        try:
            # Connect multiple clients
            for i in range(num_clients):
                uri = f"ws://localhost:{self.test_port}/ws/concurrent_test_{i}"
                client = await websockets.connect(uri)
                clients.append(client)
                
                # Send registration (just component ID)
                await client.send(json.dumps({
                    "id": f"concurrent_test_{i}"
                }))
            
            await asyncio.sleep(0.5)
            # All clients should be tracked
            self.assertEqual(len(self.server.clients), initial_count + num_clients)
            
        finally:
            # Cleanup
            for client in clients:
                await client.close()
            await asyncio.sleep(0.5)

    async def test_duplicate_path_warning(self):
        """Test warning when same path connects twice"""
        uri = f"ws://localhost:{self.test_port}/ws/duplicate_test"
        
        # First connection
        client1 = await websockets.connect(uri)
        await asyncio.sleep(0.1)
        
        # Second connection with same path (should log warning)
        client2 = await websockets.connect(uri)
        await asyncio.sleep(0.1)
        
        # Both should work but second replaces first
        self.assertEqual(self.server.clients.get("/ws/duplicate_test"), client2)
        
        await client1.close()
        await client2.close()

    # ========== Function Execution Tests ==========
    
    async def test_function_registration_and_execution(self):
        """Test function registration and remote execution"""
        result_received = asyncio.Event()
        received_data = {}
        
        def test_function(data):
            """Simple test function that doubles input"""
            return {"result": data.get("input", 0) * 2, "function": "test"}
        
        self.server.register_function(test_function)
        self.assertIn("test_function", self.server.paths)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/test_function"
        async with websockets.connect(uri) as websocket:
            # Send function call
            await websocket.send(json.dumps({
                "input": 42,
                "user_id": "test_user"
            }))
            
            # Receive result
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            received_data.update(json.loads(response))
            result_received.set()
        
        await result_received.wait()
        self.assertEqual(received_data["result"], 84)
        self.assertEqual(received_data["function"], "test")

    async def test_function_not_found_error(self):
        """Test calling non-existent function"""
        uri = f"ws://localhost:{self.test_port}/ws/functions/nonexistent_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "test": "data"
            }))
            
            # Should handle gracefully (connection might close)
            try:
                await asyncio.wait_for(websocket.recv(), timeout=2)
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                pass  # Expected behavior

    async def test_function_with_authentication_valid(self):
        """Test function execution with valid token"""
        # Mock tokens_store
        mock_tokens_store = Mock()
        mock_tokens_store.check_valid.return_value = True
        mock_tokens_store.get_user_state.return_value = {"user": "state"}
        mock_tokens_store.get_session_state.return_value = {"session": "state"}
        self.server.tokens_store = mock_tokens_store
        
        def secure_function(data):
            return {
                "secure": "data", 
                "user_state": data.get("user_state"),
                "session_state": data.get("session_state")
            }
        
        self.server.register_function(secure_function)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/secure_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "accessToken": "valid_token",
                "user_id": "test_user",
                "session_id": "test_session"
            }))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            self.assertEqual(data["secure"], "data")
            self.assertEqual(data["user_state"], {"user": "state"})
            self.assertEqual(data["session_state"], {"session": "state"})
            
        # Verify token was checked
        mock_tokens_store.check_valid.assert_called_with("valid_token")

    async def test_function_with_authentication_invalid(self):
        """Test function execution with invalid token"""
        # Mock tokens_store
        mock_tokens_store = Mock()
        mock_tokens_store.check_valid.return_value = False
        self.server.tokens_store = mock_tokens_store
        
        def secure_function(data):
            return {"should_not": "execute"}
        
        self.server.register_function(secure_function)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/secure_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "accessToken": "invalid_token",
                "user_id": "test_user"
            }))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            # Should receive error
            self.assertIn("error", data.get("data", {}).get("type", ""))

    async def test_function_without_authentication(self):
        """Test function execution when no tokens_store configured"""
        self.server.tokens_store = None
        
        def open_function(data):
            return {"open": "access", "input": data.get("input")}
        
        self.server.register_function(open_function)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/open_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "input": "test_value"
            }))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            self.assertEqual(data["open"], "access")
            self.assertEqual(data["input"], "test_value")

    async def test_function_binary_response(self):
        """Test function returning binary msgpack response"""
        def binary_function(data):
            if data.get("binary_output"):
                # Return bytes to trigger binary response
                return msgpack.packb({"binary": True, "data": [1, 2, 3]})
            return {"binary": False}
        
        self.server.register_function(binary_function)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/binary_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "binary_output": True
            }))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            
            # Response should be binary msgpack
            self.assertIsInstance(response, bytes)
            data = msgpack.unpackb(response, raw=False)
            self.assertEqual(data["binary"], True)
            self.assertEqual(data["data"], [1, 2, 3])

    # ========== Callback Tests ==========
    
    async def test_callback_registration_and_execution(self):
        """Test callback registration and triggering"""
        callback_executed = threading.Event()
        received_messages = []
        component_id = "callback_test_component"
        
        def test_callback(message):
            callback_executed.set()
            # Send data back to the component that triggered the callback
            self.server.send_data({
                "id": message.get("id"),  # Use the component ID from the message
                "response": "callback_executed",
                "input": message
            })
        
        # Register callback with component ID
        self.server.register_callback(component_id, test_callback, "test_user")
        
        uri = f"ws://localhost:{self.test_port}/ws/{component_id}"
        async with websockets.connect(uri) as websocket:
            # Send initial component registration
            await websocket.send(json.dumps({
                "id": component_id
            }))
            
            # Give time for registration
            await asyncio.sleep(0.5)
            
            # Now send a message that will trigger the callback
            await websocket.send(json.dumps({
                "id": component_id,
                "user_id": "test_user",
                "action": "trigger_callback"
            }))
            
            # Wait for callback response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                received_messages.append(json.loads(response))
            except asyncio.TimeoutError:
                self.fail("Callback response not received")
        
        self.assertTrue(callback_executed.wait(timeout=5))
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["response"], "callback_executed")

    async def test_callback_pattern_matching(self):
        """Test callback execution by pattern matching"""
        callbacks_executed = []
        
        def make_callback(name):
            def callback(msg):
                callbacks_executed.append(name)
            return callback
        
        # Register callbacks with patterns
        self.server.register_callback("prefix_test_1", make_callback("cb1"), "test_user")
        self.server.register_callback("prefix_test_2", make_callback("cb2"), "test_user")
        self.server.register_callback("other_test", make_callback("cb3"), "test_user")
        
        # Trigger by pattern
        self.server.start_callbacks_by_key("prefix_test", "session", "test_user")
        
        # Wait for execution
        await asyncio.sleep(0.5)
        
        # Should execute callbacks matching pattern
        self.assertIn("cb1", callbacks_executed)
        self.assertIn("cb2", callbacks_executed)
        self.assertNotIn("cb3", callbacks_executed)

    async def test_callback_cleanup_on_disconnect(self):
        """Test callbacks are cleaned up when client disconnects"""
        # Register callback with path
        self.server.register_callback(
            "/ws/cleanup_test/callback_1", 
            lambda m: None, 
            "test_user"
        )
        self.server.register_callback(
            "/ws/other_path/callback_2", 
            lambda m: None, 
            "test_user"
        )
        
        initial_callbacks = len(self.server.callbacks.get("test_user", {}))
        self.assertEqual(initial_callbacks, 2)
        
        uri = f"ws://localhost:{self.test_port}/ws/cleanup_test"
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "id": "cleanup_test",
                "user_id": "test_user"
            }))
            await asyncio.sleep(0.5)
        
        # After disconnect, callbacks with matching path should be removed
        await asyncio.sleep(0.5)
        remaining_callbacks = self.server.callbacks.get("test_user", {})
        
        # Callback with /ws/cleanup_test should be removed
        self.assertNotIn("/ws/cleanup_test/callback_1", remaining_callbacks)
        # Other callback should remain
        self.assertIn("/ws/other_path/callback_2", remaining_callbacks)

    async def test_callback_with_user_state(self):
        """Test callback receives user and session state"""
        received_message = {}
        message_received = threading.Event()
        
        def state_callback(message):
            received_message.update(message)
            message_received.set()
        
        # Mock tokens_store
        mock_tokens_store = Mock()
        mock_tokens_store.get_user_state.return_value = {"user": "data"}
        mock_tokens_store.get_session_state.return_value = {"session": "data"}
        self.server.tokens_store = mock_tokens_store
        
        self.server.register_callback("state_callback", state_callback, "test_user")
        
        # Trigger callback
        self.server.start_callbacks_by_key("state_callback", "test_session", "test_user")
        
        message_received.wait(timeout=2)
        
        self.assertEqual(received_message.get("user_state"), {"user": "data"})
        self.assertEqual(received_message.get("session_state"), {"session": "data"})

    # ========== Data Sending Tests ==========
    
    async def test_send_data_to_connected_client(self):
        """Test sending data to a specific connected client"""
        received_data = {}
        component_id = "send_data_test"
        
        uri = f"ws://localhost:{self.test_port}/ws/{component_id}"
        async with websockets.connect(uri) as websocket:
            # Send initial registration with just component ID
            await websocket.send(json.dumps({
                "id": component_id
            }))
            
            # Give time for registration
            await asyncio.sleep(0.5)
            
            # Send data from server in another thread
            send_thread = threading.Thread(
                target=lambda: self.server.send_data({
                    "id": component_id,  # Routes to the correct component
                    "message": "test_data",
                    "timestamp": time.time()
                })
            )
            send_thread.start()
            
            # Receive data
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                received_data.update(json.loads(response))
            except asyncio.TimeoutError:
                self.fail("Data not received from server")
            
            send_thread.join()
        
        self.assertEqual(received_data["message"], "test_data")
        self.assertIn("timestamp", received_data)

    async def test_send_data_with_numpy_types(self):
        """Test JSON encoding of numpy types"""
        component_id = "numpy_test"
        uri = f"ws://localhost:{self.test_port}/ws/{component_id}"
        received_data = {}
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "id": component_id
            }))
            
            await asyncio.sleep(0.5)
            
            # Send data with numpy types
            send_thread = threading.Thread(
                target=lambda: self.server.send_data({
                    "id": component_id,
                    "int_val": np.int64(42),
                    "float_val": np.float32(3.14),
                    "array": np.array([1, 2, 3])
                })
            )
            send_thread.start()
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            received_data = json.loads(response)
            send_thread.join()
        
        self.assertEqual(received_data["int_val"], 42)
        self.assertAlmostEqual(received_data["float_val"], 3.14, places=5)
        self.assertEqual(received_data["array"], [1, 2, 3])

    async def test_send_to_nonexistent_client(self):
        """Test sending data to non-existent client"""
        # This should just log a warning, not crash
        self.server.send_data({
            "id": "nonexistent_client",
            "data": "test"
        })
        
        # Give time for any errors
        await asyncio.sleep(0.5)
        
        # Server should still be functional - test with a real connection
        uri = f"ws://localhost:{self.test_port}/ws/test_after_error"
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "id": "test_after_error"
            }))
            # If we can still connect, test passes

    async def test_send_to_closed_connection(self):
        """Test sending data to a closed connection"""
        uri = f"ws://localhost:{self.test_port}/ws/closed_test"
        
        # Connect and immediately close
        websocket = await websockets.connect(uri)
        await websocket.send(json.dumps({
            "id": "closed_test"
        }))
        await asyncio.sleep(0.5)
        await websocket.close()
        
        # Try to send data to closed connection
        await asyncio.sleep(0.5)
        self.server.send_data({
            "id": "closed_test",
            "data": "should_not_arrive"
        })
        
        # Should handle gracefully
        await asyncio.sleep(0.5)

    # ========== Error Handling Tests ==========
    
    async def test_malformed_json_handling(self):
        """Test handling of malformed JSON messages"""
        uri = f"ws://localhost:{self.test_port}/ws/malformed_test"
        
        async with websockets.connect(uri) as websocket:
            # Send malformed JSON
            await websocket.send("{ invalid json }")
            
            # Give time for error handling
            await asyncio.sleep(0.5)
            
            # Server should still be responsive - send valid message
            await websocket.send(json.dumps({
                "id": "malformed_test",
                "user_id": "test_user"
            }))
            
            # Connection should still work
            await asyncio.sleep(0.5)

    async def test_function_exception_handling(self):
        """Test handling of exceptions in user functions"""
        def failing_function(data):
            raise ValueError("Test exception")
        
        self.server.register_function(failing_function)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/failing_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"test": "data"}))
            
            # Should receive error response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            # Should contain error information
            self.assertIn("error", data)

    async def test_callback_exception_handling(self):
        """Test handling of exceptions in callbacks"""
        def failing_callback(message):
            raise RuntimeError("Callback error")
        
        self.server.register_callback("failing_callback", failing_callback, "test_user")
        
        # Trigger callback - should not crash server
        self.server.start_callbacks_by_key("failing_callback", "session", "test_user")
        
        # Give time for execution
        await asyncio.sleep(0.5)
        
        # Server should still be functional
        uri = f"ws://localhost:{self.test_port}/ws/test_after_callback_error"
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({
                "id": "test_after_callback_error",
                "user_id": "test_user"
            }))

    # ========== Edge Cases ==========
    
    async def test_rapid_connect_disconnect(self):
        """Test rapid connection/disconnection cycles"""
        initial_clients = len(self.server.clients)
        
        for i in range(10):
            uri = f"ws://localhost:{self.test_port}/ws/rapid_test_{i}"
            websocket = await websockets.connect(uri)
            await websocket.send(json.dumps({
                "id": f"rapid_test_{i}"
            }))
            await websocket.close()
        
        # Give time for cleanup
        await asyncio.sleep(1)
        
        final_clients = len(self.server.clients)
        # All connections should be cleaned up
        self.assertEqual(final_clients, initial_clients)

    async def test_concurrent_callback_execution(self):
        """Test multiple callbacks executing concurrently"""
        callback_times = []
        callback_lock = threading.Lock()
        execution_complete = threading.Event()
        
        def timed_callback(idx):
            def callback(message):
                start = time.time()
                time.sleep(0.1)  # Simulate work
                with callback_lock:
                    callback_times.append((idx, time.time() - start))
                    if len(callback_times) == 5:
                        execution_complete.set()
            return callback
        
        # Register multiple callbacks
        for i in range(5):
            self.server.register_callback(
                f"concurrent_{i}", 
                timed_callback(i), 
                "test_user"
            )
        
        # Trigger all callbacks simultaneously
        threads = []
        start_time = time.time()
        for i in range(5):
            t = threading.Thread(
                target=lambda idx=i: self.server.start_callbacks_by_key(
                    f"concurrent_{idx}", "session", "test_user"
                )
            )
            threads.append(t)
            t.start()
        
        # Wait for completion
        execution_complete.wait(timeout=5)
        total_time = time.time() - start_time
        
        for t in threads:
            t.join()
        
        # Check all executed
        self.assertEqual(len(callback_times), 5)
        
        # Check they ran concurrently (total time should be ~0.1s, not 0.5s)
        self.assertLess(total_time, 0.3)

    async def test_large_message_handling(self):
        """Test handling of large messages"""
        large_data = {"data": "x" * 100_000}  # 100KB message
        
        def echo_function(data):
            return data
        
        self.server.register_function(echo_function)
        
        uri = f"ws://localhost:{self.test_port}/ws/functions/echo_function"
        
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps(large_data))
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            received = json.loads(response)
            self.assertEqual(len(received["data"]), 100_000)

    async def test_empty_message_handling(self):
        """Test handling of empty messages"""
        uri = f"ws://localhost:{self.test_port}/ws/empty_test"
        
        async with websockets.connect(uri) as websocket:
            # Send empty string
            await websocket.send("")
            
            # Send empty JSON object
            await websocket.send("{}")
            
            # Server should handle gracefully
            await asyncio.sleep(0.5)
            
            # Should still be able to send normal messages
            await websocket.send(json.dumps({
                "id": "empty_test",
                "user_id": "test_user"
            }))

    # ========== Helper Methods ==========
    
    async def _send_rapid_messages(self, count=100):
        """Helper to send messages rapidly"""
        for i in range(count):
            self.server.start_callbacks_by_key(
                "echo_test", f"session_{i}", "test_user"
            )
            await asyncio.sleep(0.01)
    
    async def _receive_messages(self, websocket, container, expected_count):
        """Helper to receive messages"""
        while len(container) < expected_count:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                container.append(json.loads(msg))
            except asyncio.TimeoutError:
                continue


def run_single_test(test_name):
    """Run a single test by name"""
    suite = unittest.TestSuite()
    suite.addTest(WebSocketServerTestSuite(test_name))
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


def run_all_tests():
    """Run all tests with detailed reporting"""
    import inspect
    
    # Get test class
    test_class = WebSocketServerTestSuite
    test_instance = test_class()
    
    # Setup class resources
    test_class.setUpClass()
    
    # Find all async test methods
    test_methods = []
    for name, method in inspect.getmembers(test_instance, predicate=inspect.ismethod):
        if name.startswith('test_') and asyncio.iscoroutinefunction(method):
            test_methods.append(name)
    
    # Run tests
    results = {
        "passed": [],
        "failed": [],
        "errors": []
    }
    
    async def run_tests():
        for test_name in test_methods:
            test_instance.setUp()
            try:
                print(f"Running {test_name}...", end=" ", flush=True)
                await getattr(test_instance, test_name)()
                results["passed"].append(test_name)
                print("✓ PASSED")
            except AssertionError as e:
                results["failed"].append((test_name, str(e)))
                print(f"✗ FAILED: {e}")
            except Exception as e:
                results["errors"].append((test_name, str(e)))
                print(f"✗ ERROR: {e}")
            finally:
                test_instance.tearDown()
    
    # Run async tests
    asyncio.run(run_tests())
    
    # Teardown class resources
    test_class.tearDownClass()
    
    # Summary
    print("\n" + "="*60)
    print(f"Tests Run: {len(test_methods)}")
    print(f"Passed: {len(results['passed'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Errors: {len(results['errors'])}")
    print(f"Success: {len(results['failed']) == 0 and len(results['errors']) == 0}")
    print("="*60)
    
    if results['failed']:
        print("\nFailed tests:")
        for name, error in results['failed']:
            print(f"  - {name}: {error}")
    
    if results['errors']:
        print("\nTests with errors:")
        for name, error in results['errors']:
            print(f"  - {name}: {error}")
    
    return results


async def run_async_test(test_name):
    """Helper to run async tests individually"""
    # Setup class first
    WebSocketServerTestSuite.setUpClass()
    
    suite = WebSocketServerTestSuite()
    suite.setUp()
    
    try:
        test_method = getattr(suite, test_name)
        await test_method()
        print(f"✓ {test_name} PASSED")
        return True
    except Exception as e:
        print(f"✗ {test_name} FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        suite.tearDown()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        if test_name.startswith("test_"):
            # Run async test
            loop = asyncio.get_event_loop()
            success = loop.run_until_complete(run_async_test(test_name))
            sys.exit(0 if success else 1)
        else:
            print(f"Unknown test: {test_name}")
            sys.exit(1)
    else:
        # Run all tests
        run_all_tests()