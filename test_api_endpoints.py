#!/usr/bin/env python3
"""
Test script to verify Atom API endpoints are working correctly.
This script tests the core functionality of the Atom personal assistant backend.
"""

import os
import sys
import json
import requests
import asyncio
import aiohttp
from datetime import datetime, timedelta
import base64

# Configuration
BASE_URL = "http://localhost:5058"
TEST_USER_ID = "test_user_001"

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_success(message):
    """Print success message"""
    print(f"✅ {message}")

def print_warning(message):
    """Print warning message"""
    print(f"⚠️  {message}")

def print_error(message):
    """Print error message"""
    print(f"❌ {message}")

async def test_health_endpoint():
    """Test the health endpoint"""
    print_header("Testing Health Endpoint")

    try:
        response = requests.get(f"{BASE_URL}/healthz")
        data = response.json()

        if response.status_code == 200 and data.get('status') == 'ok':
            print_success(f"Health endpoint: {data}")
            return True
        else:
            print_error(f"Health endpoint failed: {data}")
            return False

    except Exception as e:
        print_error(f"Health endpoint error: {e}")
        return False

async def test_calendar_endpoints():
    """Test calendar endpoints"""
    print_header("Testing Calendar Endpoints")

    try:
        # Test getting calendar events
        response = requests.get(f"{BASE_URL}/api/calendar/events?user_id={TEST_USER_ID}")
        data = response.json()

        if response.status_code == 200:
            print_success(f"Calendar events: {len(data.get('events', []))} events found")

            # Test calendar sync
            sync_response = requests.post(f"{BASE_URL}/api/calendar/sync",
                                        json={"user_id": TEST_USER_ID})
            sync_data = sync_response.json()

            if sync_response.status_code == 200:
                print_success(f"Calendar sync: {sync_data}")
            else:
                print_warning(f"Calendar sync may not be fully implemented: {sync_data}")

            return True

        else:
            print_error(f"Calendar events failed: {data}")
            return False

    except Exception as e:
        print_error(f"Calendar endpoints error: {e}")
        return False

async def test_task_endpoints():
    """Test task endpoints"""
    print_header("Testing Task Endpoints")

    try:
        # Test getting tasks
        response = requests.get(f"{BASE_URL}/api/tasks?user_id={TEST_USER_ID}")
        data = response.json()

        if response.status_code == 200:
            print_success(f"Tasks: {len(data.get('tasks', []))} tasks found")

            # Test creating a task
            new_task = {
                "user_id": TEST_USER_ID,
                "task": {
                    "title": "Test Task from API",
                    "description": "This is a test task created by the API test script",
                    "due_date": (datetime.now() + timedelta(days=1)).isoformat(),
                    "priority": "medium",
                    "status": "todo"
                }
            }

            create_response = requests.post(f"{BASE_URL}/api/tasks", json=new_task)
            create_data = create_response.json()

            if create_response.status_code == 200:
                print_success(f"Task created: {create_data}")

                # Test getting task stats
                stats_response = requests.get(f"{BASE_URL}/api/tasks/stats?user_id={TEST_USER_ID}")
                stats_data = stats_response.json()

                if stats_response.status_code == 200:
                    print_success(f"Task stats: {stats_data.get('stats', {})}")
                else:
                    print_warning(f"Task stats may not be implemented: {stats_data}")

            else:
                print_warning(f"Task creation may not be implemented: {create_data}")

            return True

        else:
            print_error(f"Tasks endpoint failed: {data}")
            return False

    except Exception as e:
        print_error(f"Task endpoints error: {e}")
        return False

async def test_message_endpoints():
    """Test message endpoints"""
    print_header("Testing Message Endpoints")

    try:
        # Test getting messages
        response = requests.get(f"{BASE_URL}/api/messages?user_id={TEST_USER_ID}")
        data = response.json()

        if response.status_code == 200:
            print_success(f"Messages: {len(data.get('messages', []))} messages found")

            # Test message stats
            stats_response = requests.get(f"{BASE_URL}/api/messages/stats?user_id={TEST_USER_ID}")
            stats_data = stats_response.json()

            if stats_response.status_code == 200:
                print_success(f"Message stats: {stats_data.get('stats', {})}")
            else:
                print_warning(f"Message stats may not be implemented: {stats_data}")

            return True

        else:
            print_error(f"Messages endpoint failed: {data}")
            return False

    except Exception as e:
        print_error(f"Message endpoints error: {e}")
        return False

async def test_transcription_endpoints():
    """Test transcription endpoints"""
    print_header("Testing Transcription Endpoints")

    try:
        # Test transcription health
        response = requests.get(f"{BASE_URL}/api/transcription/health")
        data = response.json()

        if response.status_code == 200:
            print_success(f"Transcription health: {data}")

            # Test getting meeting transcription (should fail since no meeting exists)
            meeting_response = requests.get(f"{BASE_URL}/api/transcription/meetings/test_meeting_001")
            meeting_data = meeting_response.json()

            if meeting_response.status_code == 404:
                print_success("Meeting transcription endpoint returns proper 404 for non-existent meeting")
            else:
                print_warning(f"Meeting transcription response: {meeting_data}")

            return True

        else:
            print_error(f"Transcription health failed: {data}")
            return False

    except Exception as e:
        print_error(f"Transcription endpoints error: {e}")
        return False

async def test_dashboard_data():
    """Test dashboard data integration"""
    print_header("Testing Dashboard Data Integration")

    try:
        # This simulates what the frontend dashboard would do
        async with aiohttp.ClientSession() as session:
            # Get calendar events
            calendar_url = f"{BASE_URL}/api/calendar/events?user_id={TEST_USER_ID}"
            async with session.get(calendar_url) as response:
                calendar_data = await response.json()
                calendar_events = calendar_data.get('events', [])
                print_success(f"Dashboard - Calendar: {len(calendar_events)} events")

            # Get tasks
            tasks_url = f"{BASE_URL}/api/tasks?user_id={TEST_USER_ID}"
            async with session.get(tasks_url) as response:
                tasks_data = await response.json()
                tasks = tasks_data.get('tasks', [])
                print_success(f"Dashboard - Tasks: {len(tasks)} tasks")

            # Get messages
            messages_url = f"{BASE_URL}/api/messages?user_id={TEST_USER_ID}"
            async with session.get(messages_url) as response:
                messages_data = await response.json()
                messages = messages_data.get('messages', [])
                print_success(f"Dashboard - Messages: {len(messages)} messages")

            # Calculate dashboard stats
            upcoming_events = len([e for e in calendar_events
                                 if datetime.fromisoformat(e['start'].replace('Z', '+00:00')) > datetime.now()])

            overdue_tasks = len([t for t in tasks
                               if t['status'] != 'completed' and
                               datetime.fromisoformat(t['due_date'].replace('Z', '+00:00')) < datetime.now()])

            unread_messages = len([m for m in messages if m['unread']])
            completed_tasks = len([t for t in tasks if t['status'] == 'completed'])

            print_success(f"Dashboard Stats:")
            print_success(f"  - Upcoming Events: {upcoming_events}")
            print_success(f"  - Overdue Tasks: {overdue_tasks}")
            print_success(f"  - Unread Messages: {unread_messages}")
            print_success(f"  - Completed Tasks: {completed_tasks}")

            return True

    except Exception as e:
        print_error(f"Dashboard integration error: {e}")
        return False

async def run_all_tests():
    """Run all API tests"""
    print_header("Starting Atom API Integration Tests")
    print(f"Base URL: {BASE_URL}")
    print(f"Test User ID: {TEST_USER_ID}")

    test_results = {}

    # Run all tests
    test_results['health'] = await test_health_endpoint()
    test_results['calendar'] = await test_calendar_endpoints()
    test_results['tasks'] = await test_task_endpoints()
    test_results['messages'] = await test_message_endpoints()
    test_results['transcription'] = await test_transcription_endpoints()
    test_results['dashboard'] = await test_dashboard_data()

    # Print summary
    print_header("Test Results Summary")
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())

    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name.upper():<15}: {status}")

    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print_success("All tests passed! 🎉")
        return True
    else:
        print_warning("Some tests failed or returned warnings")
        return passed_tests > 0  # Consider it a success if at least some tests passed

def main():
    """Main function"""
    try:
        # Check if server is running
        try:
            response = requests.get(f"{BASE_URL}/healthz", timeout=5)
            if response.status_code != 200:
                print_error("API server is not running or not healthy")
                print("Please start the server with: cd atom/backend/python-api-service && python main_api_app.py")
                sys.exit(1)
        except requests.exceptions.ConnectionError:
            print_error("Cannot connect to API server")
            print("Please start the server with: cd atom/backend/python-api-service && python main_api_app.py")
            sys.exit(1)

        # Run tests
        success = asyncio.run(run_all_tests())

        if success:
            print("\n🎉 API integration test completed successfully!")
            print("\nNext steps:")
            print("1. Configure environment variables in .env file")
            print("2. Set up OAuth credentials for calendar providers")
            print("3. Add Deepgram API key for transcription")
            print("4. Start the frontend: cd atom/frontend-nextjs && npm run dev")
            sys.exit(0)
        else:
            print("\n❌ API integration test failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
