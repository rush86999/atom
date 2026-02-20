"""
Comprehensive test suite for Conflict Resolution Service

Tests conflict detection, severity scoring, merge strategies,
sync integration, rating conflicts, and admin endpoints.

Phase 61 Plan 04 - Conflict Resolution
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from core.conflict_resolution_service import ConflictResolutionService
from core.models import ConflictLog, SkillCache, SkillRating


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def local_skill(db_session):
    """Sample local skill data"""
    return {
        "skill_id": "test-skill-001",
        "name": "Data Processor",
        "description": "Local version",
        "version": "1.0.0",
        "code": "def process():\n    return 'local'",
        "python_packages": ["pandas==1.3.0"],
        "npm_packages": [],
        "tags": ["data", "processing"],
        "metadata": {"author": "local"}
    }


@pytest.fixture
def remote_skill(db_session):
    """Sample remote skill data"""
    return {
        "skill_id": "test-skill-001",
        "name": "Data Processor",
        "description": "Remote version",
        "version": "1.1.0",
        "code": "def process():\n    return 'remote'",
        "python_packages": ["pandas==1.4.0"],
        "npm_packages": [],
        "tags": ["data", "analytics"],
        "metadata": {"author": "remote"}
    }


@pytest.fixture
def local_rating(db_session):
    """Sample local rating"""
    rating = SkillRating(
        skill_id="test-skill-001",
        user_id="user@example.com",
        rating=5,
        comment="Great skill!",
        created_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db.add(rating)
    db.commit()
    return rating


# ============================================================================
# Test Conflict Detection
# ============================================================================

class TestConflictDetection:
    """Test conflict detection logic"""

    def test_version_mismatch_detected(self, db_session, local_skill, remote_skill):
        """VERSION_MISMATCH detected when versions differ"""
        resolver = ConflictResolutionService(db)

        conflict_type = resolver.detect_skill_conflict(local_skill, remote_skill)

        assert conflict_type == "VERSION_MISMATCH"

    def test_content_mismatch_detected(self, db_session):
        """CONTENT_MISMATCH detected when code differs"""
        resolver = ConflictResolutionService(db)

        local = {
            "skill_id": "test-001",
            "version": "1.0.0",
            "code": "local code"
        }
        remote = {
            "skill_id": "test-001",
            "version": "1.0.0",  # Same version
            "code": "remote code"  # Different code
        }

        conflict_type = resolver.detect_skill_conflict(local, remote)

        assert conflict_type == "CONTENT_MISMATCH"

    def test_dependency_conflict_detected(self, db_session):
        """DEPENDENCY_CONFLICT detected when packages differ"""
        resolver = ConflictResolutionService(db)

        local = {
            "skill_id": "test-001",
            "version": "1.0.0",
            "code": "same code",
            "python_packages": ["pandas==1.3.0"]
        }
        remote = {
            "skill_id": "test-001",
            "version": "1.0.0",
            "code": "same code",  # Same code
            "python_packages": ["pandas==1.4.0"]  # Different packages
        }

        conflict_type = resolver.detect_skill_conflict(local, remote)

        assert conflict_type == "DEPENDENCY_CONFLICT"

    def test_no_conflict_when_identical(self, db_session):
        """No conflict when skills are identical"""
        resolver = ConflictResolutionService(db)

        skill = {
            "skill_id": "test-001",
            "version": "1.0.0",
            "code": "same code"
        }

        conflict_type = resolver.detect_skill_conflict(skill, skill)

        assert conflict_type is None

    def test_severity_critical_for_code_change(self, db_session):
        """CRITICAL severity when code differs"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "code": "local code"}
        remote = {"skill_id": "test-001", "code": "remote code"}

        severity = resolver.calculate_severity(local, remote, "CONTENT_MISMATCH")

        assert severity == "CRITICAL"

    def test_severity_high_for_version_change(self, db_session):
        """HIGH severity when version differs"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "version": "1.0.0"}
        remote = {"skill_id": "test-001", "version": "2.0.0"}

        severity = resolver.calculate_severity(local, remote, "VERSION_MISMATCH")

        assert severity == "HIGH"

    def test_severity_low_for_description_change(self, db_session):
        """LOW severity when only description differs"""
        resolver = ConflictResolutionService(db)

        local = {
            "skill_id": "test-001",
            "version": "1.0.0",
            "code": "same code",
            "description": "Local description"
        }
        remote = {
            "skill_id": "test-001",
            "version": "1.0.0",
            "code": "same code",
            "description": "Remote description"
        }

        severity = resolver.calculate_severity(local, remote, "OTHER")

        assert severity == "LOW"

    def test_compare_versions_true(self, db_session):
        """compare_versions returns True when versions differ"""
        resolver = ConflictResolutionService(db)

        result = resolver.compare_versions(
            {"version": "1.0.0"},
            {"version": "1.1.0"}
        )

        assert result is True

    def test_compare_versions_false(self, db_session):
        """compare_versions returns False when versions match"""
        resolver = ConflictResolutionService(db)

        result = resolver.compare_versions(
            {"version": "1.0.0"},
            {"version": "1.0.0"}
        )

        assert result is False

    def test_compare_content_true(self, db_session):
        """compare_content returns True when code differs"""
        resolver = ConflictResolutionService(db)

        result = resolver.compare_content(
            {"code": "local code"},
            {"code": "remote code"}
        )

        assert result is True

    def test_compare_dependencies_true(self, db_session):
        """compare_dependencies returns True when packages differ"""
        resolver = ConflictResolutionService(db)

        result = resolver.compare_dependencies(
            {"python_packages": ["pandas==1.0.0"]},
            {"python_packages": ["pandas==1.1.0"]}
        )

        assert result is True

    def test_calculate_content_hash(self, db_session):
        """calculate_content_hash generates SHA256 hash"""
        resolver = ConflictResolutionService(db)

        skill_data = {
            "skill_id": "test-001",
            "name": "Test Skill",
            "code": "print('hello')"
        }

        hash_value = resolver.calculate_content_hash(skill_data)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA256 hex length


# ============================================================================
# Test Conflict Strategies
# ============================================================================

class TestConflictStrategies:
    """Test merge strategies"""

    def test_remote_wins_returns_remote(self, db_session):
        """remote_wins returns remote skill data"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "name": "Local"}
        remote = {"skill_id": "test-001", "name": "Remote"}

        result = resolver.remote_wins(local, remote)

        assert result == remote

    def test_local_wins_returns_local(self, db_session):
        """local_wins returns local skill data"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "name": "Local"}
        remote = {"skill_id": "test-001", "name": "Remote"}

        result = resolver.local_wins(local, remote)

        assert result == local

    def test_merge_combines_fields(self, db_session):
        """merge strategy combines fields intelligently"""
        resolver = ConflictResolutionService(db)

        local = {
            "skill_id": "test-001",
            "description": "Local desc",
            "tags": ["local"],
            "code": "local code",
            "python_packages": ["numpy"],
            "version": "1.0.0"
        }
        remote = {
            "skill_id": "test-001",
            "description": "Remote desc - much longer",
            "tags": ["remote"],
            "code": "remote code",
            "python_packages": ["pandas"],
            "version": "2.0.0"
        }

        result = resolver.merge(local, remote)

        # Automatic fields: use most recent (longer description)
        assert result["description"] == remote["description"]

        # Critical fields: keep local
        assert result["code"] == local["code"]

        # Dependencies: merge both sets
        assert set(result["python_packages"]) == {"numpy", "pandas"}

        # Version: merged format
        assert "merged" in result["version"]

    def test_merge_preserves_critical_fields(self, db_session):
        """merge preserves critical fields from local"""
        resolver = ConflictResolutionService(db)

        local = {
            "skill_id": "test-001",
            "code": "local code",
            "command": "python run.py",
            "local_files": ["config.json"]
        }
        remote = {
            "skill_id": "test-001",
            "code": "remote code",
            "command": "python run_remote.py",
            "local_files": ["remote_config.json"]
        }

        result = resolver.merge(local, remote)

        assert result["code"] == local["code"]
        assert result["command"] == local["command"]
        assert result["local_files"] == local["local_files"]

    def test_manual_logs_conflict(self, db_session):
        """manual strategy logs conflict to database"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "name": "Local"}
        remote = {"skill_id": "test-001", "name": "Remote"}

        result = resolver.manual(
            local,
            remote,
            skill_id="test-001",
            conflict_type="CONTENT_MISMATCH",
            severity="HIGH"
        )

        # Returns None (no automatic resolution)
        assert result is None

        # Conflict logged to database
        conflicts = resolver.get_unresolved_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].skill_id == "test-001"


# ============================================================================
# Test Merge Logic
# ============================================================================

class TestMergeLogic:
    """Test merge strategy logic in detail"""

    def test_automatic_fields_use_most_recent(self, db_session):
        """Automatic fields (description, tags, examples, metadata) use most recent"""
        resolver = ConflictResolutionService(db)

        # Test description (longer = more recent)
        local = {"skill_id": "test-001", "description": "Short"}
        remote = {"skill_id": "test-001", "description": "Much longer description with more details"}

        result = resolver.merge(local, remote)
        assert result["description"] == remote["description"]

        # Test tags (more tags = more recent)
        local = {"skill_id": "test-001", "tags": ["a"]}
        remote = {"skill_id": "test-001", "tags": ["a", "b", "c"]}

        result = resolver.merge(local, remote)
        assert result["tags"] == remote["tags"]

    def test_dependencies_union(self, db_session):
        """Dependencies merged as union (no duplicates)"""
        resolver = ConflictResolutionService(db)

        local = {
            "skill_id": "test-001",
            "python_packages": ["numpy==1.0.0", "pandas==1.0.0"],
            "npm_packages": ["lodash"]
        }
        remote = {
            "skill_id": "test-001",
            "python_packages": ["pandas==1.0.0", "requests==2.0.0"],  # pandas duplicate
            "npm_packages": ["axios"]
        }

        result = resolver.merge(local, remote)

        # Union of packages, sorted, no duplicates
        assert set(result["python_packages"]) == {"numpy==1.0.0", "pandas==1.0.0", "requests==2.0.0"}
        assert set(result["npm_packages"]) == {"lodash", "axios"}

    def test_version_format_merged(self, db_session):
        """Merged version has correct format: local+merged+remote"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "version": "1.0.0"}
        remote = {"skill_id": "test-001", "version": "2.0.0"}

        result = resolver.merge(local, remote)

        assert result["version"] == "1.0.0+merged+2.0.0"


# ============================================================================
# Test Sync Integration
# ============================================================================

class TestSyncIntegration:
    """Test conflict resolution integration with sync"""

    def test_auto_resolve_no_conflict(self, db_session):
        """auto_resolve_conflict returns remote when no conflict"""
        resolver = ConflictResolutionService(db)

        skill = {"skill_id": "test-001", "version": "1.0.0"}

        result = resolver.auto_resolve_conflict(skill, skill, "remote_wins")

        assert result == skill

    def test_auto_resolve_with_conflict(self, db_session):
        """auto_resolve_conflict applies strategy when conflict detected"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "name": "Local"}
        remote = {"skill_id": "test-001", "name": "Remote"}

        result = resolver.auto_resolve_conflict(local, remote, "remote_wins")

        assert result == remote

    def test_auto_resolve_manual_logs_conflict(self, db_session):
        """auto_resolve_conflict with manual strategy logs conflict"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "name": "Local"}
        remote = {"skill_id": "test-001", "name": "Remote"}

        result = resolver.auto_resolve_conflict(local, remote, "manual")

        # Returns None (manual resolution needed)
        assert result is None

        # Conflict logged
        conflicts = resolver.get_unresolved_conflicts()
        assert len(conflicts) == 1

    def test_log_conflict_creates_record(self, db_session):
        """log_conflict creates ConflictLog record"""
        resolver = ConflictResolutionService(db)

        conflict = resolver.log_conflict(
            skill_id="test-001",
            conflict_type="VERSION_MISMATCH",
            severity="HIGH",
            local_data={"version": "1.0.0"},
            remote_data={"version": "2.0.0"}
        )

        assert conflict.id is not None
        assert conflict.skill_id == "test-001"
        assert conflict.conflict_type == "VERSION_MISMATCH"
        assert conflict.severity == "HIGH"
        assert conflict.resolved_at is None

    def test_get_unresolved_conflicts(self, db_session):
        """get_unresolved_conflicts returns unresolved conflicts"""
        resolver = ConflictResolutionService(db)

        # Create 3 conflicts
        for i in range(3):
            resolver.log_conflict(
                skill_id=f"test-{i}",
                conflict_type="VERSION_MISMATCH",
                severity="HIGH",
                local_data={},
                remote_data={}
            )

        # Get unresolved
        conflicts = resolver.get_unresolved_conflicts()

        assert len(conflicts) == 3

    def test_get_conflict_by_id(self, db_session):
        """get_conflict_by_id returns specific conflict"""
        resolver = ConflictResolutionService(db)

        conflict = resolver.log_conflict(
            skill_id="test-001",
            conflict_type="VERSION_MISMATCH",
            severity="HIGH",
            local_data={},
            remote_data={}
        )

        fetched = resolver.get_conflict_by_id(conflict.id)

        assert fetched is not None
        assert fetched.id == conflict.id


# ============================================================================
# Test Rating Conflicts
# ============================================================================

class TestRatingConflicts:
    """Test rating conflict resolution"""

    def test_rating_conflict_logged(self, db_session, local_rating):
        """Rating conflicts are logged to ConflictLog"""
        from core.rating_sync_service import RatingSyncService

        sync_service = RatingSyncService(db)

        remote_rating = {
            "id": "remote-123",
            "rating": 4,  # Different from local (5)
            "comment": "Updated comment",
            "created_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        }

        # Resolve conflict
        result = sync_service.resolve_rating_conflict(local_rating, remote_rating)

        # Conflict should be logged
        conflicts = db.query(ConflictLog).filter(
            ConflictLog.skill_id == local_rating.skill_id
        ).all()

        assert len(conflicts) > 0

    def test_rating_conflict_newest_wins(self, db_session, local_rating):
        """Newest rating wins based on timestamp"""
        from core.rating_sync_service import RatingSyncService

        sync_service = RatingSyncService(db)

        # Remote is newer (future timestamp)
        remote_rating = {
            "id": "remote-123",
            "rating": 3,  # Different rating
            "comment": "Newer comment",
            "created_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        }

        result = sync_service.resolve_rating_conflict(local_rating, remote_rating)

        # Local should be updated to match remote
        assert local_rating.rating == 3
        assert local_rating.comment == "Newer comment"


# ============================================================================
# Test Admin Endpoints (Integration)
# ============================================================================

class TestAdminEndpoints:
    """Test admin conflict management endpoints"""

    def test_list_conflicts_filter_by_severity(self, db_session):
        """Can filter conflicts by severity"""
        resolver = ConflictResolutionService(db)

        # Create conflicts with different severities
        resolver.log_conflict("test-1", "VERSION_MISMATCH", "LOW", {}, {})
        resolver.log_conflict("test-2", "VERSION_MISMATCH", "HIGH", {})

        # Filter by HIGH severity
        high_conflicts = resolver.get_unresolved_conflicts(severity="HIGH")

        assert len(high_conflicts) == 1
        assert high_conflicts[0].severity == "HIGH"

    def test_list_conflicts_filter_by_type(self, db_session):
        """Can filter conflicts by type"""
        resolver = ConflictResolutionService(db)

        # Create conflicts with different types
        resolver.log_conflict("test-1", "VERSION_MISMATCH", "LOW", {}, {})
        resolver.log_conflict("test-2", "CONTENT_MISMATCH", "HIGH", {})

        # Filter by CONTENT_MISMATCH type
        content_conflicts = resolver.get_unresolved_conflicts(conflict_type="CONTENT_MISMATCH")

        assert len(content_conflicts) == 1
        assert content_conflicts[0].conflict_type == "CONTENT_MISMATCH"

    def test_resolve_conflict_updates_log(self, db_session):
        """resolve_conflict updates ConflictLog record"""
        resolver = ConflictResolutionService(db)

        # Create conflict
        conflict = resolver.log_conflict(
            skill_id="test-001",
            conflict_type="VERSION_MISMATCH",
            severity="HIGH",
            local_data={"version": "1.0.0"},
            remote_data={"version": "2.0.0"}
        )

        # Resolve conflict
        resolved_data = resolver.resolve_conflict(
            conflict_id=conflict.id,
            strategy="remote_wins",
            resolved_by="admin@example.com"
        )

        # Verify conflict resolved
        assert resolved_data is not None
        assert conflict.resolved_at is not None
        assert conflict.resolved_by == "admin@example.com"
        assert conflict.resolution_strategy == "remote_wins"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_none_values_in_comparison(self, db_session):
        """Comparisons handle None values gracefully"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "version": None}
        remote = {"skill_id": "test-001", "version": "1.0.0"}

        # Should not crash
        conflict_type = resolver.detect_skill_conflict(local, remote)
        assert conflict_type is not None

    def test_empty_packages_list(self, db_session):
        """Empty package lists don't cause conflicts"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "python_packages": []}
        remote = {"skill_id": "test-001", "python_packages": []}

        result = resolver.compare_dependencies(local, remote)

        assert result is False  # No conflict

    def test_large_json_data(self, db_session):
        """Large JSON data in conflict log handled correctly"""
        resolver = ConflictResolutionService(db)

        large_data = {"key": "value" * 10000}  # Large data

        conflict = resolver.log_conflict(
            skill_id="test-001",
            conflict_type="OTHER",
            severity="LOW",
            local_data=large_data,
            remote_data=large_data
        )

        assert conflict is not None
        assert conflict.id is not None

    def test_resolve_nonexistent_conflict(self, db_session):
        """Resolving non-existent conflict returns None"""
        resolver = ConflictResolutionService(db)

        result = resolver.resolve_conflict(
            conflict_id=99999,  # Non-existent
            strategy="remote_wins",
            resolved_by="admin@example.com"
        )

        assert result is None

    def test_invalid_strategy_in_auto_resolve(self, db_session):
        """Invalid strategy in auto_resolve_conflict handled gracefully"""
        resolver = ConflictResolutionService(db)

        local = {"skill_id": "test-001", "name": "Local"}
        remote = {"skill_id": "test-001", "name": "Remote"}

        # Invalid strategy
        result = resolver.auto_resolve_conflict(local, remote, "invalid_strategy")

        assert result is None
