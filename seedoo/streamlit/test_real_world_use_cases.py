#!/usr/bin/env python3
"""
Comprehensive real-world use case tests for WebSocket event server.
Tests actual client scenarios and edge cases.
"""

import asyncio
import websockets
import json
import msgpack
import time
import threading
import sys
import os
import uuid
import numpy as np
from typing import List, Dict, Any
from collections import defaultdict
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_server import WebSocketServer

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class RealWorldTestSuite:
    """Test suite for real-world WebSocket server use cases"""
    
    def __init__(self):
        self.server = None
        self.test_port = 9902
        self.results = {}
        
    async def setup(self):
        """Setup test environment"""
        self.server = WebSocketServer("localhost", self.test_port)
        self.server.start_server()
        await asyncio.sleep(2)  # Let server start
        
    async def teardown(self):
        """Cleanup test environment"""
        # Clear callbacks and paths
        self.server.callbacks.clear()
        self.server.paths.clear()
        await asyncio.sleep(0.5)

    # ========== Test 1: Modal Dialog Workflow ==========
    
    async def test_modal_dialog_workflow(self):
        """Test modal open → user interaction → save → close flow"""
        modal_id = "test_modal_123"
        received_events = []
        form_data_received = {}
        
        # Register modal callback
        def modal_callback(message):
            action = message.get("action")
            if action == "save":
                form_data_received.update(message.get("form_data", {}))
                # Send close event
                self.server.send_data({
                    "id": modal_id,
                    "event": "close",
                    "showModal": False
                })
        
        self.server.register_callback(modal_id, modal_callback, "test_user")
        
        # Connect as modal component
        uri = f"ws://localhost:{self.test_port}/ws/{modal_id}"
        async with websockets.connect(uri) as ws:
            # Register component
            await ws.send(json.dumps({"id": modal_id}))
            
            # Collect events
            async def collect_events():
                try:
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                        received_events.append(json.loads(msg))
                except asyncio.TimeoutError:
                    pass
            
            event_task = asyncio.create_task(collect_events())
            
            # Simulate opening modal
            self.server.send_data({
                "id": modal_id,
                "event": "open",
                "showModal": True,
                "title": "User Settings",
                "fields": ["name", "email"]
            })
            
            await asyncio.sleep(0.5)
            
            # Simulate user filling form and saving
            await ws.send(json.dumps({
                "id": modal_id,
                "user_id": "test_user",
                "action": "save",
                "form_data": {
                    "name": "John Doe",
                    "email": "john@example.com"
                }
            }))
            
            await asyncio.sleep(1)
            event_task.cancel()
        
        # Verify flow
        assert len(received_events) >= 2, "Should receive open and close events"
        assert received_events[0]["event"] == "open", "First event should be open"
        assert received_events[0]["showModal"] == True, "Modal should be shown"
        assert received_events[-1]["event"] == "close", "Last event should be close"
        assert received_events[-1]["showModal"] == False, "Modal should be hidden"
        assert form_data_received["name"] == "John Doe", "Form data should be received"

    # ========== Test 2: WebSocket Button Loading States ==========
    
    async def test_websocket_button_loading_states(self):
        """Test button state transitions during long operation"""
        button_id = "process_button"
        state_changes = []
        
        def button_callback(message):
            # Send loading state immediately
            self.server.send_data({
                "id": button_id,
                "event": "state_change",
                "spinner": True,
                "disabled": True,
                "text": "Processing..."
            })
            
            # Simulate processing
            time.sleep(1)  # Simulating work
            
            # Send completion state
            self.server.send_data({
                "id": button_id,
                "event": "state_change",
                "spinner": False,
                "disabled": False,
                "text": "Process Data",
                "result": {"processed": True, "count": 42}
            })
        
        self.server.register_callback(button_id, button_callback, "test_user")
        
        uri = f"ws://localhost:{self.test_port}/ws/{button_id}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"id": button_id}))
            
            # Click button
            click_time = time.time()
            await ws.send(json.dumps({
                "id": button_id,
                "user_id": "test_user",
                "clicked": True
            }))
            
            # Collect state changes
            while len(state_changes) < 2:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    data = json.loads(msg)
                    state_changes.append({
                        "data": data,
                        "time": time.time() - click_time
                    })
                except asyncio.TimeoutError:
                    break
        
        # Verify state transitions
        assert len(state_changes) == 2, "Should receive 2 state changes"
        assert state_changes[0]["data"]["spinner"] == True, "First state should show spinner"
        assert state_changes[0]["data"]["disabled"] == True, "Button should be disabled"
        assert state_changes[0]["time"] < 0.2, "Loading state should appear quickly"
        assert state_changes[1]["data"]["spinner"] == False, "Final state should hide spinner"
        assert state_changes[1]["data"]["result"]["count"] == 42, "Should receive result"
        assert 0.9 < state_changes[1]["time"] < 1.5, "Processing should take ~1 second"

    # ========== Test 3: Real-time Dashboard Updates ==========
    
    async def test_realtime_dashboard_updates(self):
        """Test periodic updates from background thread"""
        dashboard_id = "metrics_dashboard"
        updates_received = []
        stop_updates = threading.Event()
        
        def send_updates():
            """Background thread sending updates"""
            counter = 0
            while not stop_updates.is_set():
                self.server.send_data({
                    "id": dashboard_id,
                    "event": "metrics_update",
                    "data": {
                        "cpu": 45.5 + counter,
                        "memory": 2048 + counter * 10,
                        "requests": counter * 5,
                        "timestamp": time.time()
                    }
                })
                counter += 1
                time.sleep(0.5)
        
        # Start background updates
        update_thread = threading.Thread(target=send_updates, daemon=True)
        update_thread.start()
        
        uri = f"ws://localhost:{self.test_port}/ws/{dashboard_id}"
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"id": dashboard_id}))
                
                # Collect 5 updates
                start_time = time.time()
                while len(updates_received) < 5:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    updates_received.append({
                        "data": json.loads(msg),
                        "time": time.time() - start_time
                    })
        finally:
            stop_updates.set()
            update_thread.join()
        
        # Verify updates
        assert len(updates_received) == 5, "Should receive 5 updates"
        
        # Check timing
        for i in range(1, len(updates_received)):
            time_diff = updates_received[i]["time"] - updates_received[i-1]["time"]
            assert 0.4 < time_diff < 0.6, f"Updates should be ~500ms apart, got {time_diff}"
        
        # Check data changes
        for i in range(1, len(updates_received)):
            prev_cpu = updates_received[i-1]["data"]["data"]["cpu"]
            curr_cpu = updates_received[i]["data"]["data"]["cpu"]
            assert curr_cpu > prev_cpu, "CPU values should increase"

    # ========== Test 4: Collaborative Editing Broadcast ==========
    
    async def test_collaborative_editing_broadcast(self):
        """Test broadcasting changes to multiple connected clients"""
        editor_id = "collab_editor"
        user_messages = defaultdict(list)
        
        def editor_callback(message):
            user_id = message.get("user_id")
            action = message.get("action")
            
            if action == "edit":
                # Broadcast to all OTHER users
                for other_user in ["user_1", "user_2", "user_3"]:
                    if other_user != user_id:
                        self.server.send_data({
                            "id": f"{editor_id}_{other_user}",
                            "event": "remote_edit",
                            "from_user": user_id,
                            "changes": message.get("changes")
                        })
        
        # Register callback for each user
        for user in ["user_1", "user_2", "user_3"]:
            self.server.register_callback(editor_id, editor_callback, user)
        
        # Connect 3 users
        connections = {}
        for user in ["user_1", "user_2", "user_3"]:
            uri = f"ws://localhost:{self.test_port}/ws/{editor_id}_{user}"
            connections[user] = await websockets.connect(uri)
            await connections[user].send(json.dumps({"id": f"{editor_id}_{user}"}))
        
        # User 1 makes an edit
        await connections["user_1"].send(json.dumps({
            "id": editor_id,
            "user_id": "user_1",
            "action": "edit",
            "changes": {"line": 5, "text": "Hello from user 1"}
        }))
        
        # Collect messages for each user
        await asyncio.sleep(1.0)  # Give more time for messages to propagate
        for user, ws in connections.items():
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                user_messages[user].append(json.loads(msg))
            except asyncio.TimeoutError:
                pass
        
        # Close connections
        for ws in connections.values():
            await ws.close()
        
        # Verify broadcasting
        # Note: In our implementation, messages are routed to specific component IDs
        # So we need to ensure proper routing
        assert len(user_messages["user_1"]) == 0, "User 1 should not receive own edit"
        assert len(user_messages["user_2"]) >= 1, "User 2 should receive edit"
        assert len(user_messages["user_3"]) >= 1, "User 3 should receive edit"
        
        # Verify message content
        for user in ["user_2", "user_3"]:
            msg = user_messages[user][0]
            assert msg["event"] == "remote_edit"
            assert msg["from_user"] == "user_1"
            assert msg["changes"]["text"] == "Hello from user 1"

    # ========== Test 5: File Upload Progress ==========
    
    async def test_file_upload_progress(self):
        """Test chunked upload with progress notifications"""
        uploader_id = "file_uploader"
        progress_updates = []
        
        def upload_callback(message):
            chunk_index = message.get("chunk_index")
            total_chunks = message.get("total_chunks")
            progress = ((chunk_index + 1) / total_chunks) * 100
            
            self.server.send_data({
                "id": uploader_id,
                "event": "progress",
                "file_id": message.get("file_id"),
                "progress": progress,
                "status": "complete" if progress >= 100 else "uploading"
            })
        
        self.server.register_callback(uploader_id, upload_callback, "test_user")
        
        uri = f"ws://localhost:{self.test_port}/ws/{uploader_id}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"id": uploader_id}))
            
            # Send 10 chunks
            file_id = str(uuid.uuid4())
            for i in range(10):
                await ws.send(json.dumps({
                    "id": uploader_id,
                    "user_id": "test_user",
                    "action": "upload_chunk",
                    "file_id": file_id,
                    "chunk_index": i,
                    "total_chunks": 10,
                    "data": f"chunk_{i}_data"
                }))
                
                # Receive progress update
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                progress_updates.append(json.loads(msg))
        
        # Verify progress
        assert len(progress_updates) == 10, "Should receive 10 progress updates"
        
        # Check progress values
        expected_progress = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for i, update in enumerate(progress_updates):
            assert update["progress"] == expected_progress[i], f"Progress should be {expected_progress[i]}%"
            assert update["file_id"] == file_id
            
        # Check final status
        assert progress_updates[-1]["status"] == "complete"
        assert all(u["status"] == "uploading" for u in progress_updates[:-1])

    # ========== Test 6: Form Validation Flow ==========
    
    async def test_form_validation_workflow(self):
        """Test field-by-field validation with error messages"""
        form_id = "registration_form"
        
        def validation_callback(message):
            field = message.get("field")
            value = message.get("value")
            
            result = {
                "id": form_id,
                "event": "validation",
                "field": field,
                "valid": True,
                "error": None
            }
            
            if field == "email":
                if "@" not in value:
                    result["valid"] = False
                    result["error"] = "Invalid email format"
                elif value == "taken@example.com":
                    result["valid"] = False
                    result["error"] = "Email already registered"
            elif field == "username":
                if len(value) < 3:
                    result["valid"] = False
                    result["error"] = "Username too short"
            
            self.server.send_data(result)
        
        self.server.register_callback(form_id, validation_callback, "test_user")
        
        uri = f"ws://localhost:{self.test_port}/ws/{form_id}"
        validation_results = []
        
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"id": form_id}))
            
            # Test cases
            test_cases = [
                {"field": "email", "value": "invalid", "expect_valid": False},
                {"field": "email", "value": "taken@example.com", "expect_valid": False},
                {"field": "email", "value": "good@example.com", "expect_valid": True},
                {"field": "username", "value": "ab", "expect_valid": False},
                {"field": "username", "value": "gooduser", "expect_valid": True},
            ]
            
            for test in test_cases:
                start_time = time.time()
                await ws.send(json.dumps({
                    "id": form_id,
                    "user_id": "test_user",
                    "action": "validate",
                    "field": test["field"],
                    "value": test["value"]
                }))
                
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                result = json.loads(msg)
                result["response_time"] = time.time() - start_time
                validation_results.append(result)
        
        # Verify validations
        assert len(validation_results) == 5
        
        for i, result in enumerate(validation_results):
            test = test_cases[i]
            assert result["field"] == test["field"]
            assert result["valid"] == test["expect_valid"]
            assert result["response_time"] < 0.1, "Validation should be fast"
            
            if not result["valid"]:
                assert result["error"] is not None

    # ========== Test 7: User-Specific Notifications ==========
    
    async def test_user_specific_notifications(self):
        """Test routing notifications to specific users"""
        user_notifications = defaultdict(list)
        
        # Connect 3 users
        connections = {}
        for user_id in ["user_1", "user_2", "user_3"]:
            notification_id = f"notifications_{user_id}"
            uri = f"ws://localhost:{self.test_port}/ws/{notification_id}"
            connections[user_id] = await websockets.connect(uri)
            await connections[user_id].send(json.dumps({"id": notification_id}))
        
        # Send notification to user_2 only
        self.server.send_data({
            "id": "notifications_user_2",
            "event": "new_notification",
            "notification": {
                "id": str(uuid.uuid4()),
                "title": "Task Complete",
                "message": "Your analysis is ready",
                "type": "success"
            }
        })
        
        # Send broadcast notification
        for user_id in ["user_1", "user_2", "user_3"]:
            self.server.send_data({
                "id": f"notifications_{user_id}",
                "event": "new_notification",
                "notification": {
                    "id": str(uuid.uuid4()),
                    "title": "System Update",
                    "message": "Maintenance scheduled",
                    "type": "info"
                }
            })
        
        # Collect notifications
        await asyncio.sleep(0.5)
        for user_id, ws in connections.items():
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    user_notifications[user_id].append(json.loads(msg))
                except asyncio.TimeoutError:
                    break
            await ws.close()
        
        # Verify routing
        assert len(user_notifications["user_1"]) == 1, "User 1 should get only broadcast"
        assert len(user_notifications["user_2"]) == 2, "User 2 should get targeted + broadcast"
        assert len(user_notifications["user_3"]) == 1, "User 3 should get only broadcast"
        
        # Verify user_2 got the targeted notification
        user_2_titles = [n["notification"]["title"] for n in user_notifications["user_2"]]
        assert "Task Complete" in user_2_titles
        assert "System Update" in user_2_titles

    # ========== Test 8: Error Recovery ==========
    
    async def test_error_recovery_scenarios(self):
        """Test recovery from callback errors"""
        error_id = "error_test"
        execution_log = []
        
        def failing_callback(message):
            execution_log.append("failing")
            raise ValueError("Intentional error")
        
        def working_callback(message):
            execution_log.append("working")
            self.server.send_data({
                "id": error_id,
                "status": "success"
            })
        
        # Register both callbacks
        self.server.register_callback(f"{error_id}_fail", failing_callback, "test_user")
        self.server.register_callback(f"{error_id}_work", working_callback, "test_user")
        
        uri = f"ws://localhost:{self.test_port}/ws/{error_id}"
        responses = []
        
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"id": error_id}))
            
            # Trigger failing callback
            await ws.send(json.dumps({
                "id": f"{error_id}_fail",
                "user_id": "test_user"
            }))
            
            await asyncio.sleep(0.5)
            
            # Trigger working callback
            await ws.send(json.dumps({
                "id": f"{error_id}_work",
                "user_id": "test_user"
            }))
            
            # Collect responses
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                responses.append(json.loads(msg))
            except asyncio.TimeoutError:
                pass
        
        # Verify error recovery
        assert "failing" in execution_log
        assert "working" in execution_log
        assert len(responses) == 1
        assert responses[0]["status"] == "success"

    # ========== Test 9: High Concurrency Stress Test ==========
    
    async def test_high_concurrency_stress(self):
        """Test system under high concurrent load"""
        num_clients = 20
        messages_per_client = 5
        received_messages = defaultdict(list)
        
        # Register echo callback
        def echo_callback(message):
            client_id = message.get("client_id")
            seq = message.get("seq")
            self.server.send_data({
                "id": f"stress_test_{client_id}",
                "echo": seq,
                "processed": True
            })
        
        self.server.register_callback("stress_echo", echo_callback, "test_user")
        
        async def client_task(client_id):
            uri = f"ws://localhost:{self.test_port}/ws/stress_test_{client_id}"
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"id": f"stress_test_{client_id}"}))
                
                # Send messages
                for seq in range(messages_per_client):
                    await ws.send(json.dumps({
                        "id": "stress_echo",
                        "user_id": "test_user",
                        "client_id": client_id,
                        "seq": seq
                    }))
                
                # Receive echoes
                for _ in range(messages_per_client):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        data = json.loads(msg)
                        received_messages[client_id].append(data["echo"])
                    except asyncio.TimeoutError:
                        break
        
        # Run all clients concurrently
        start_time = time.time()
        await asyncio.gather(*[client_task(i) for i in range(num_clients)])
        duration = time.time() - start_time
        
        # Verify results
        total_sent = num_clients * messages_per_client
        total_received = sum(len(msgs) for msgs in received_messages.values())
        
        assert total_received == total_sent, f"Should receive all {total_sent} messages"
        assert duration < 10, "Should complete within 10 seconds"
        
        # Verify each client got correct messages
        for client_id in range(num_clients):
            client_msgs = sorted(received_messages[client_id])
            expected = list(range(messages_per_client))
            assert client_msgs == expected, f"Client {client_id} should receive all its messages in order"

    # ========== Test 10: Binary Data Transfer ==========
    
    async def test_binary_data_transfer(self):
        """Test msgpack binary transfer efficiency"""
        
        def data_function(message):
            # Return large numpy array
            size = message.get("size", 1000)
            data = np.random.rand(size, size).astype(np.float32)
            
            if message.get("binary"):
                # Return dict (server will msgpack encode it)
                return {
                    "array_shape": list(data.shape),
                    "array_data": data.tobytes(),
                    "dtype": str(data.dtype)
                }
            else:
                # Return as JSON (will use custom encoder)
                return {"array": data.tolist()}
        
        self.server.register_function(data_function)
        
        # Test binary transfer
        binary_uri = f"ws://localhost:{self.test_port}/ws/functions/data_function"
        
        async with websockets.connect(binary_uri) as ws:
            # Request binary data
            start_time = time.time()
            await ws.send(json.dumps({
                "size": 100,
                "binary": True
            }))
            
            binary_response = await asyncio.wait_for(ws.recv(), timeout=5)
            binary_time = time.time() - start_time
            binary_size = len(binary_response)
        
        # Test JSON transfer
        async with websockets.connect(binary_uri) as ws:
            # Request JSON data
            start_time = time.time()
            await ws.send(json.dumps({
                "size": 100,
                "binary": False
            }))
            
            json_response = await asyncio.wait_for(ws.recv(), timeout=5)
            json_time = time.time() - start_time
            json_size = len(json_response)
        
        # Verify binary is more efficient
        assert binary_size < json_size * 0.5, "Binary should be <50% of JSON size"
        assert binary_time < json_time, "Binary should be faster"
        
        # Verify data integrity
        binary_data = msgpack.unpackb(binary_response)
        assert binary_data["array_shape"] == [100, 100]
        assert binary_data["dtype"] == "float32"

    # ========== Test Runner ==========
    
    async def run_all_tests(self):
        """Run all tests and collect results"""
        test_methods = [
            method for method in dir(self)
            if method.startswith('test_') and callable(getattr(self, method))
        ]
        
        print("Running Real-World WebSocket Server Tests")
        print("=" * 60)
        
        for test_name in test_methods:
            print(f"\nRunning {test_name}...", end=" ", flush=True)
            start_time = time.time()
            
            try:
                test_method = getattr(self, test_name)
                await test_method()
                duration = time.time() - start_time
                print(f"✓ PASSED ({duration:.2f}s)")
                self.results[test_name] = {
                    "status": "PASS",
                    "duration": duration
                }
            except Exception as e:
                duration = time.time() - start_time
                print(f"✗ FAILED ({duration:.2f}s)")
                print(f"  Error: {str(e)}")
                self.results[test_name] = {
                    "status": "FAIL",
                    "error": str(e),
                    "duration": duration
                }
                
                # Reset server state after failure
                self.server.callbacks.clear()
                await asyncio.sleep(0.5)
        
        # Generate report
        self.generate_report()
        
    def generate_report(self):
        """Generate test report"""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed = sum(1 for r in self.results.values() if r["status"] == "PASS")
        failed = total_tests - passed
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total_tests)*100:.1f}%")
        
        if failed > 0:
            print("\nFailed Tests:")
            for test_name, result in self.results.items():
                if result["status"] == "FAIL":
                    print(f"  - {test_name}: {result['error']}")
        
        # Performance summary
        print("\nPerformance Summary:")
        durations = [r["duration"] for r in self.results.values()]
        print(f"  Total Time: {sum(durations):.2f}s")
        print(f"  Average Test Time: {sum(durations)/len(durations):.2f}s")
        print(f"  Slowest Test: {max(durations):.2f}s")


async def main():
    """Run the test suite"""
    suite = RealWorldTestSuite()
    await suite.setup()
    
    try:
        await suite.run_all_tests()
    finally:
        await suite.teardown()
    
    # Return exit code based on results
    failed_count = sum(1 for r in suite.results.values() if r["status"] == "FAIL")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)