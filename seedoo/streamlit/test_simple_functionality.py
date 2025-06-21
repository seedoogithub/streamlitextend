#!/usr/bin/env python3
"""
Simple test to verify basic WebSocket server functionality after changes.
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

async def test_basic_functionality():
    """Test basic server functionality"""
    print("Starting WebSocket server...")
    server = WebSocketServer("localhost", 9900)
    server.start_server()
    await asyncio.sleep(2)
    
    print("\n1. Testing basic connection...")
    uri = "ws://localhost:9900/ws/test_client"
    async with websockets.connect(uri) as ws:
        print("✓ Connected successfully")
        
        # Send registration
        await ws.send(json.dumps({
            "id": "test_client",
            "user_id": "test_user"
        }))
        print("✓ Sent registration message")
    
    print("\n2. Testing send_data functionality...")
    messages_received = []
    
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "id": "test_client",
            "user_id": "test_user"
        }))
        
        # Start receiver task
        async def receive_messages():
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    messages_received.append(json.loads(msg))
                    print(f"✓ Received: {msg[:50]}...")
            except asyncio.TimeoutError:
                pass
        
        receive_task = asyncio.create_task(receive_messages())
        
        # Send data from another thread
        def send_test_data():
            time.sleep(0.5)
            print("  Sending data from thread...")
            server.send_data({
                "id": "test_client",
                "message": "Hello from server!",
                "timestamp": time.time()
            })
        
        send_thread = threading.Thread(target=send_test_data)
        send_thread.start()
        
        # Wait for message
        await asyncio.sleep(2)
        receive_task.cancel()
        send_thread.join()
    
    if messages_received:
        print(f"✓ Data sending works! Received {len(messages_received)} messages")
    else:
        print("✗ No messages received")
    
    print("\n3. Testing callback functionality...")
    callback_executed = threading.Event()
    
    def test_callback(message):
        print("  ✓ Callback executed!")
        callback_executed.set()
        server.send_data({
            "id": "test_client",
            "callback_response": "Callback worked!"
        })
    
    server.register_callback("test_callback", test_callback, "test_user")
    print("✓ Callback registered")
    
    # Trigger callback
    print("  Triggering callback...")
    server.start_callbacks_by_key("test_callback", "session_123", "test_user")
    
    if callback_executed.wait(timeout=2):
        print("✓ Callback system works!")
    else:
        print("✗ Callback not executed")
    
    print("\n4. Testing function execution...")
    def test_function(data):
        return {"result": data.get("input", 0) * 2, "status": "success"}
    
    server.register_function(test_function)
    print("✓ Function registered")
    
    uri_func = "ws://localhost:9900/ws/functions/test_function"
    async with websockets.connect(uri_func) as ws:
        await ws.send(json.dumps({
            "input": 21,
            "user_id": "test_user"
        }))
        
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(response)
        if data.get("result") == 42:
            print("✓ Function execution works!")
        else:
            print(f"✗ Unexpected result: {data}")
    
    print("\n✅ All basic functionality tests completed!")
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_basic_functionality())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()