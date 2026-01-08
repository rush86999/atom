"""
Test Data Visibility Implementation
"""
import sys
sys.path.append('backend')

def test_visibility():
    print("=== Data Visibility Test ===\n")
    
    # 1. Test DataVisibility enum
    from core.data_visibility import DataVisibility
    print("1. DataVisibility Enum:")
    for v in DataVisibility:
        print(f"   - {v.name}: {v.value}")
    
    # 2. Test can_access function
    from core.data_visibility import can_access
    
    class MockTeam:
        def __init__(self, id):
            self.id = id
    
    class MockUser:
        def __init__(self, id, team_ids):
            self.id = id
            self.teams = [MockTeam(tid) for tid in team_ids]
    
    class MockResource:
        def __init__(self, visibility, owner_id, team_id):
            self.visibility = visibility
            self.owner_id = owner_id
            self.team_id = team_id
    
    user_a = MockUser("user_a", ["team_1"])
    user_b = MockUser("user_b", ["team_2"])
    
    # Test private visibility
    private_resource = MockResource("private", "user_a", None)
    assert can_access(user_a, private_resource) == True, "Owner should access private"
    assert can_access(user_b, private_resource) == False, "Non-owner should NOT access private"
    print("\n2. Private visibility: ✓")
    
    # Test team visibility
    team_resource = MockResource("team", "user_a", "team_1")
    assert can_access(user_a, team_resource) == True, "Team member should access"
    assert can_access(user_b, team_resource) == False, "Non-team member should NOT access"
    print("3. Team visibility: ✓")
    
    # Test workspace visibility
    workspace_resource = MockResource("workspace", "user_a", None)
    assert can_access(user_a, workspace_resource) == True
    assert can_access(user_b, workspace_resource) == True
    print("4. Workspace visibility: ✓")
    
    # 3. Test models have visibility
    from core.models import WorkflowExecution, ChatProcess
    assert hasattr(WorkflowExecution, 'visibility')
    assert hasattr(ChatProcess, 'visibility')
    print("\n5. Models have visibility columns: ✓")
    
    print("\n=== All Tests Passed ===")

if __name__ == "__main__":
    test_visibility()
