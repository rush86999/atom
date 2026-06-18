"""
Test suite for Mass Assignment vulnerabilities.

RED PHASE: These tests expose mass assignment bugs.

The bugs:
1. user_templates_endpoints.py:366 - Template update uses setattr() with user input
2. workflow_template_routes.py:158 - Template update uses request.dict() without filtering
"""

import pytest
import inspect


class TestMassAssignmentVulnerabilities:
    """
    Test suite revealing mass assignment vulnerabilities.

    The bug: User input is automatically bound to object properties without
    proper field filtering, allowing attackers to modify sensitive fields.
    """

    def test_user_template_update_uses_setattr_with_user_input(self):
        """
        Test that user template update uses setattr() with user-provided data.

        BUG: Lines 395-401 - All fields from request are updated via setattr()
        without filtering sensitive fields like owner_id, created_at, etc.
        """
        from api.user_templates_endpoints import update_template

        source = inspect.getsource(update_template)

        # Verify the bug - request.dict() is used to get all fields
        assert 'request.dict(' in source, \
            "Bug confirmed: request.dict() extracts all user-provided fields"

        # Verify setattr is used to update fields
        assert 'setattr(template' in source, \
            "Bug confirmed: setattr() updates template with user data"

        # Verify that fields are not explicitly filtered (except change_description)
        assert "exclude={'change_description'}" in source or 'exclude_unset=True' in source, \
            "Bug confirmed: Only change_description is excluded, other fields not filtered"

    def test_user_template_update_allows_owner_modification(self):
        """
        Test that user template update allows modifying owner_id.

        BUG: Lines 395-401 - sensitive fields like owner_id can be modified
        by an attacker using mass assignment.
        """
        from api.user_templates_endpoints import update_template

        source = inspect.getsource(update_template)

        # Verify the bug - no explicit check for sensitive fields
        # An attacker could include owner_id in the request
        assert 'for field, value in update_data.items()' in source, \
            "Bug confirmed: Loop iterates over all user-provided fields"

        # No filtering of owner_id field
        assert "field == 'owner_id'" not in source, \
            "Bug confirmed: No check for owner_id modification"

        # No filtering of created_at field
        assert "field == 'created_at'" not in source, \
            "Bug confirmed: No check for created_at modification"

    def test_workflow_template_update_uses_request_dict(self):
        """
        Test that workflow template update uses request.dict() without filtering.

        BUG: Line 158 - request.dict() is used to extract all fields
        without filtering sensitive fields.
        """
        from api.workflow_template_routes import update_template_endpoint

        source = inspect.getsource(update_template_endpoint)

        # Verify the bug - request.dict() extracts all fields
        assert 'request.dict()' in source, \
            "Bug confirmed: request.dict() extracts all user-provided fields"

        # Verify updates are passed to manager without additional filtering
        assert 'manager.update_template(template_id, updates)' in source or 'update_template(template_id, updates)' in source, \
            "Bug confirmed: All user-provided fields passed to update without filtering"

    def test_workflow_template_update_allows_sensitive_field_modification(self):
        """
        Test that workflow template update allows modifying sensitive fields.

        BUG: An attacker could include owner_id, is_public, or other
        sensitive fields in the request to gain unauthorized access.
        """
        from api.workflow_template_routes import update_template_endpoint

        source = inspect.getsource(update_template_endpoint)

        # Verify no explicit filtering of sensitive fields
        assert "'owner_id'" not in source or "owner_id in" not in source, \
            "Bug confirmed: No filtering for owner_id field"

        # The code only filters None values, not sensitive fields
        assert 'if v is not None' in source, \
            "Bug confirmed: Only None values are filtered, not sensitive fields"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
