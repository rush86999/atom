#!/usr/bin/env python3
"""
Comprehensive test script for Goals API endpoints.
Run with: python test_goals_api.py
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:5058"
TEST_USER_ID = "test_user_123"

def run_tests():
    """Run comprehensive tests for the goals API."""
    print("🎯 Testing Goals API...")
    print("=" * 50)

    # Test user
    user_id = TEST_USER_ID

    try:
        # 1. Test creating a new goal
        print("\n1️⃣ Testing goal creation...")
        goal_data = {
            "userId": user_id,
            "title": "Emergency Fund",
            "description": "Build up emergency fund for unexpected expenses",
            "targetAmount": 10000,
            "goalType": "emergency_fund",
            "targetDate": (datetime.now() + timedelta(days=365)).isoformat().split('T')[0],
            "priority": 1,
            "initialAmount": 1500
        }

        response = requests.post(
            f"{BASE_URL}/api/goals",
            json=goal_data
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        created_goal = response.json()
        goal_id = created_goal['id']
        print(f"✅ Created goal ID: {goal_id}")

        # 2. Test getting all goals
        print("\n2️⃣ Testing getting all goals...")
        response = requests.get(
            f"{BASE_URL}/api/goals",
            params={"userId": user_id}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        goals = response.json()['goals']
        assert len(goals) > 0, "Expected at least one goal"
        print(f"✅ Found {len(goals)} goals")

        # 3. Test getting specific goal
        print("\n3️⃣ Testing getting specific goal...")
        response = requests.get(
            f"{BASE_URL}/api/goals/{goal_id}",
            params={"userId": user_id}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        goal = response.json()
        assert goal['id'] == goal_id, "Goal ID mismatch"
        print("✅ Retrieved goal successfully")

        # 4. Test updating goal
        print("\n4️⃣ Testing goal update...")
        update_data = {
            "userId": user_id,
            "title": "Emergency Fund - Updated",
            "currentAmount": 1750,
            "priority": 2
        }
        response = requests.put(
            f"{BASE_URL}/api/goals/{goal_id}",
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        updated_goal = response.json()
        assert updated_goal['title'] == "Emergency Fund - Updated"
        print("✅ Updated goal successfully")

        # 5. Test adding contribution
        print("\n5️⃣ Testing contribution addition...")
        contribution_data = {
            "userId": user_id,
            "amount": 500,
            "description": "Monthly contribution",
            "sourceAccountId": 1
        }
        response = requests.post(
            f"{BASE_URL}/api/goals/{goal_id}/contribute",
            json=contribution_data
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        contribution = response.json()
        assert contribution['amount'] == 500
        print("✅ Added contribution successfully")

        # 6. Test getting contributions
        print("\n6️⃣ Testing getting contributions...")
        response = requests.get(
            f"{BASE_URL}/api/goals/{goal_id}/contributions",
            params={"userId": user_id}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        contributions = response.json()['contributions']
        assert len(contributions) > 0, "Expected at least one contribution"
        print(f"✅ Found {len(contributions)} contributions")

        # 7. Test filtering by goal type
        print("\n7️⃣ Testing goal type filtering...")
        response = requests.get(
            f"{BASE_URL}/api/goals",
            params={"userId": user_id, "goalType": "emergency_fund"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        filtered_goals = response.json()['goals']
        assert all(g['goal_type'] == 'emergency_fund' for g in filtered
