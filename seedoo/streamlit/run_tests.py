#!/usr/bin/env python3
"""
Run a subset of critical tests to verify functionality.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_event_server_comprehensive import WebSocketServerTestSuite

async def run_critical_tests():
    """Run critical tests to verify core functionality"""
    # Setup
    WebSocketServerTestSuite.setUpClass()
    suite = WebSocketServerTestSuite()
    
    critical_tests = [
        "test_client_connection_tracking",
        "test_function_registration_and_execution", 
        "test_callback_registration_and_execution",
        "test_send_data_to_connected_client",
        "test_send_data_with_numpy_types",
        "test_concurrent_callback_execution"
    ]
    
    results = {"passed": 0, "failed": 0}
    
    for test_name in critical_tests:
        suite.setUp()
        try:
            print(f"\nRunning {test_name}...", flush=True)
            test_method = getattr(suite, test_name)
            await test_method()
            print(f"✓ {test_name} PASSED")
            results["passed"] += 1
        except Exception as e:
            print(f"✗ {test_name} FAILED: {e}")
            results["failed"] += 1
        finally:
            suite.tearDown()
            await asyncio.sleep(0.5)  # Give time between tests
    
    # Summary
    print("\n" + "="*60)
    print(f"Critical Tests Summary:")
    print(f"  Passed: {results['passed']}/{len(critical_tests)}")
    print(f"  Failed: {results['failed']}/{len(critical_tests)}")
    print("="*60)
    
    return results["failed"] == 0

if __name__ == "__main__":
    success = asyncio.run(run_critical_tests())
    sys.exit(0 if success else 1)