#!/usr/bin/env python3
"""
Test script for ChatProcessManager.
Run with: python test_chat_process.py
"""

import asyncio
import sys
import os
import logging
logging.basicConfig(level=logging.DEBUG)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.chat_process_manager import get_process_manager


async def test_chat_process_manager():
    """Test the ChatProcessManager functionality"""
    print("=== Testing ChatProcessManager ===\n")

    manager = get_process_manager()
    user_id = "test_user_123"
    process_name = "Test Multi-Step Process"

    # Define steps
    steps = [
        {
            "id": "step1",
            "title": "Get Name",
            "description": "What is your name?",
            "requiredInput": "name"
        },
        {
            "id": "step2",
            "title": "Get Email",
            "description": "What is your email?",
            "requiredInput": "email"
        },
        {
            "id": "step3",
            "title": "Confirmation",
            "description": "Confirm details",
            "requiredInput": ""
        }
    ]

    # 1. Create a new process
    print("1. Creating new process...")
    process_id = await manager.create_process(
        user_id=user_id,
        name=process_name,
        steps=steps,
        initial_context={"source": "test"}
    )
    print(f"   Created process ID: {process_id}")

    # 2. Retrieve the process
    print("\n2. Retrieving process...")
    process = await manager.get_process(process_id)
    if not process:
        print("   ERROR: Process not found!")
        return
    print(f"   Process name: {process['name']}")
    print(f"   Current step: {process['current_step']}")
    print(f"   Total steps: {process['total_steps']}")
    print(f"   Status: {process['status']}")

    # 3. Submit input for step 1
    print("\n3. Submitting input for step 1...")
    result = await manager.update_process_step(
        process_id=process_id,
        step_input={"name": "John Doe"},
        step_output={"greeting": "Hello John"},
        missing_parameters=None
    )
    print(f"   Next step: {result['next_step']}")
    print(f"   Status: {result['status']}")
    print(f"   Missing parameters: {result['missing_parameters']}")

    # 4. Check process state after step 1
    process = await manager.get_process(process_id)
    print(f"   Current step after update: {process['current_step']}")
    print(f"   Inputs collected: {process['inputs']}")
    print(f"   Outputs collected: {process['outputs']}")

    # 5. Submit input for step 2 with missing parameters
    print("\n4. Submitting input for step 2 with missing parameters...")
    result = await manager.update_process_step(
        process_id=process_id,
        step_input={"email": ""},  # Empty email
        step_output=None,
        missing_parameters=["email"]  # Simulate missing parameter
    )
    print(f"   Next step: {result['next_step']}")
    print(f"   Status: {result['status']}")
    print(f"   Missing parameters: {result['missing_parameters']}")

    # 6. Check process is paused
    process = await manager.get_process(process_id)
    print(f"   Process status after missing param: {process['status']}")
    print(f"   Missing parameters in DB: {process['missing_parameters']}")

    # 7. Resume process with missing parameter
    print("\n5. Resuming process with missing parameter...")
    result = await manager.resume_process(
        process_id=process_id,
        new_inputs={"email": "john@example.com"}
    )
    print(f"   Status after resume: {result['status']}")
    print(f"   Remaining missing: {result['remaining_missing']}")

    # 8. Complete final step
    print("\n6. Completing final step...")
    result = await manager.update_process_step(
        process_id=process_id,
        step_input={"confirmed": True},
        step_output={"final": "Process completed successfully"},
        missing_parameters=None
    )
    print(f"   Next step: {result['next_step']}")
    print(f"   Status: {result['status']}")

    # 9. Get final process state
    process = await manager.get_process(process_id)
    print(f"\n7. Final process state:")
    print(f"   Status: {process['status']}")
    print(f"   Current step: {process['current_step']}")
    print(f"   Inputs: {process['inputs']}")
    print(f"   Outputs: {process['outputs']}")

    # 10. Get user's processes
    print("\n8. Listing user's processes...")
    processes = await manager.get_user_processes(user_id)
    print(f"   Found {len(processes)} processes for user {user_id}")
    for p in processes:
        print(f"   - {p['name']} (ID: {p['id']}, Status: {p['status']})")

    print("\n=== Test completed successfully ===")


if __name__ == "__main__":
    asyncio.run(test_chat_process_manager())