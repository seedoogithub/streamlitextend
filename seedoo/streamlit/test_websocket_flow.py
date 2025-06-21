#!/usr/bin/env python3
"""
Test WebSocket server with correct message flow and data structures.
"""

import asyncio
import websockets
import json
import time
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_server import WebSocketServer

async def test_correct_flow():
    """Test server with correct message structures"""
    print("Starting WebSocket server...")
    server = WebSocketServer("localhost", 9901)
    server.start_server()
    await asyncio.sleep(2)
    
    print("\n1. Testing send_data with correct flow...")
    
    # Connect as a component with ID "my_component"
    component_id = "my_component"
    uri = f"ws://localhost:9901/ws/{component_id}"
    
    messages_received = []
    
    async with websockets.connect(uri) as ws:
        print(f"✓ Connected to {uri}")
        
        # This is what the frontend component would send on initialization
        await ws.send(json.dumps({
            "id": component_id  # Just the component ID, no user_id here
        }))
        print("✓ Sent component registration")
        
        # Start receiver
        async def receive_messages():
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)
                    messages_received.append(data)
                    print(f"✓ Received: {data}")
            except asyncio.TimeoutError:
                pass
            except websockets.exceptions.ConnectionClosed:
                pass
        
        receive_task = asyncio.create_task(receive_messages())
        
        # Now send data from server to this specific component
        def send_to_component():
            time.sleep(0.5)
            print(f"  Sending data to component '{component_id}'...")
            server.send_data({
                "id": component_id,  # This ID routes to the correct WebSocket
                "event": "update",
                "data": {"message": "Hello from server!"}
            })
        
        send_thread = threading.Thread(target=send_to_component)
        send_thread.start()
        
        # Wait for message
        await asyncio.sleep(2)
        receive_task.cancel()
        send_thread.join()
    
    if messages_received:
        print(f"✓ send_data works! Received {len(messages_received)} messages")
    else:
        print("✗ No messages received via send_data")
    
    print("\n2. Testing callback execution with correct message...")
    
    # Register a callback that will be triggered when component sends a message
    callback_executed = threading.Event()
    received_callback_data = {}
    
    def my_callback(message):
        print(f"  ✓ Callback executed with message: {message}")
        received_callback_data.update(message)
        callback_executed.set()
        # Send response back to component
        server.send_data({
            "id": message.get("id"),  # Send back to same component
            "event": "callback_response",
            "data": {"status": "callback executed"}
        })
    
    # Register callback with component ID
    server.register_callback(component_id, my_callback, "test_user")
    print(f"✓ Registered callback for component '{component_id}'")
    
    # Now simulate component sending a message that triggers the callback
    messages_received.clear()
    
    async with websockets.connect(uri) as ws:
        # Component sends a message with its ID
        await ws.send(json.dumps({
            "id": component_id,
            "user_id": "test_user",  # This is used to look up callbacks
            "action": "button_click",
            "value": "test_value"
        }))
        print("✓ Component sent trigger message")
        
        # Receive callback response
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3)
            response = json.loads(msg)
            print(f"✓ Received callback response: {response}")
        except asyncio.TimeoutError:
            print("✗ No callback response received")
    
    if callback_executed.wait(timeout=2):
        print("✓ Callback system works correctly!")
        print(f"  Callback received data: {received_callback_data}")
    else:
        print("✗ Callback was not executed")
    
    print("\n3. Testing function execution...")
    
    def my_function(data):
        print(f"  Function called with: {data}")
        return {
            "result": data.get("input", 0) * 2,
            "echo": data.get("echo", ""),
            "status": "success"
        }
    
    server.register_function(my_function)
    print("✓ Registered function 'my_function'")
    
    # Function calls use a different path pattern
    func_uri = "ws://localhost:9901/ws/functions/my_function"
    
    async with websockets.connect(func_uri) as ws:
        # Send function call
        await ws.send(json.dumps({
            "input": 21,
            "echo": "test",
            "user_id": "test_user"
            # Note: no 'id' field needed for function calls
        }))
        
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(response)
        print(f"✓ Function response: {data}")
        
        if data.get("result") == 42:
            print("✓ Function execution works correctly!")
        else:
            print(f"✗ Unexpected result: {data}")
    
    print("\n✅ All tests completed!")
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_correct_flow())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()