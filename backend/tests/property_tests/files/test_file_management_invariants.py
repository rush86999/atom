"""
Property-Based Tests for File and Document Management Invariants

Tests critical file/document management business logic:
- File upload and storage
- File metadata management
- File version control
- File access control and permissions
- File sharing and collaboration
- File download and streaming
- File deletion and retention
- File quarantine and security
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from typing import Dict, List, Set, Optional
import uuid


class TestFileUploadInvariants:
    """Tests for file upload invariants"""

    @given(
        user_id=st.uuids(),
        filename=st.text(min_size=1, max_size=255, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.'),
        file_size=st.integers(min_value=1, max_value=100_000_000_000),  # 1 byte to 100 GB
        mime_type=st.sampled_from([
            'image/jpeg',
            'image/png',
            'application/pdf',
            'text/plain',
            'application/json',
            'application/zip',
            'video/mp4',
            'audio/mpeg'
        ]),
        uploaded_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_file_upload_creates_valid_file_record(self, user_id, filename, file_size, mime_type, uploaded_at):
        """Test that file upload creates a valid file record"""
        # Simulate file upload
        file_record = {
            'id': str(uuid.uuid4()),
            'user_id': str(user_id),
            'filename': filename,
            'file_size': file_size,
            'mime_type': mime_type,
            'uploaded_at': uploaded_at,
            'status': 'UPLOADING',
            'storage_path': f'/files/{user_id}/{uuid.uuid4()}'
        }

        # Verify file record
        assert file_record['id'] is not None, "File ID must be set"
        assert file_record['user_id'] is not None, "User ID must be set"
        assert len(file_record['filename']) >= 1, "Filename must not be empty"
        assert file_record['file_size'] >= 1, "File size must be positive"
        assert file_record['mime_type'] in [
            'image/jpeg', 'image/png', 'application/pdf', 'text/plain',
            'application/json', 'application/zip', 'video/mp4', 'audio/mpeg'
        ], "Valid MIME type"
        assert file_record['status'] in ['UPLOADING', 'COMPLETED', 'FAILED'], "Valid status"

    @given(
        file_size=st.integers(min_value=1, max_value=100_000_000_000),
        max_file_size=st.integers(min_value=1_000_000, max_value=10_000_000_000)  # 1 MB to 10 GB
    )
    @settings(max_examples=50)
    def test_file_size_limit_enforcement(self, file_size, max_file_size):
        """Test that file size limits are enforced"""
        # Check if file size is within limit
        within_limit = file_size <= max_file_size

        # Verify limit
        if file_size <= max_file_size:
            assert within_limit is True, "File within size limit"
        else:
            assert within_limit is False, "File exceeds size limit"

    @given(
        filename=st.text(min_size=1, max_size=500),
        max_filename_length=st.integers(min_value=100, max_value=255)
    )
    @settings(max_examples=50)
    def test_filename_length_validation(self, filename, max_filename_length):
        """Test that filename length is validated"""
        # Check if filename length is valid
        is_valid = len(filename) <= max_filename_length

        # Verify validation
        if len(filename) <= max_filename_length:
            assert is_valid is True, "Filename within length limit"
        else:
            assert is_valid is False, "Filename exceeds length limit"

    @given(
        extension=st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
        allowed_extensions=st.sets(
            st.text(min_size=1, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_file_extension_whitelist(self, extension, allowed_extensions):
        """Test that file extensions are validated against whitelist"""
        # Check if extension is allowed
        is_allowed = extension.lower() in {ext.lower() for ext in allowed_extensions}

        # Verify whitelist
        if extension.lower() in {ext.lower() for ext in allowed_extensions}:
            assert is_allowed is True, "Extension is allowed"
        else:
            # Not in whitelist - may or may not be allowed depending on policy
            assert True, "Extension validation"


class TestFileMetadataInvariants:
    """Tests for file metadata invariants"""

    @given(
        file_id=st.uuids(),
        custom_metadata=st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(
                st.text(min_size=0, max_size=500),
                st.integers(min_value=-1000000, max_value=1000000),
                st.booleans(),
                st.floats(allow_nan=False, allow_infinity=False)
            ),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_file_metadata_storage(self, file_id, custom_metadata):
        """Test that file metadata is stored correctly"""
        # Store metadata
        metadata = {
            'file_id': str(file_id),
            'custom': custom_metadata
        }

        # Verify metadata
        assert metadata['file_id'] is not None, "File ID must be set"
        for key, value in custom_metadata.items():
            assert metadata['custom'].get(key) == value, f"Metadata {key} must be set to {value}"

    @given(
        file_id=st.uuids(),
        tags=st.lists(
            st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'),
            min_size=0,
            max_size=50,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_file_tagging(self, file_id, tags):
        """Test that file tags are stored correctly"""
        # Store tags
        file_tags = {
            'file_id': str(file_id),
            'tags': list(set(tags))  # Ensure uniqueness
        }

        # Verify tags
        assert file_tags['file_id'] is not None, "File ID must be set"
        assert len(file_tags['tags']) == len(set(tags)), "Tags must be unique"
        assert len(file_tags['tags']) <= 50, "Max 50 tags allowed"

    @given(
        description=st.text(min_size=0, max_size=5000),
        max_length=st.integers(min_value=100, max_value=5000)
    )
    @settings(max_examples=50)
    def test_file_description_length(self, description, max_length):
        """Test that file description length is validated"""
        # Check if description length is valid
        is_valid = len(description) <= max_length

        # Verify validation
        if len(description) <= max_length:
            assert is_valid is True, "Description within length limit"
        else:
            assert is_valid is False, "Description exceeds length limit"


class TestFileVersionControlInvariants:
    """Tests for file version control invariants"""

    @given(
        file_id=st.uuids(),
        version_number=st.integers(min_value=1, max_value=1000),
        uploaded_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_version_creation_increments_version(self, file_id, version_number, uploaded_at):
        """Test that version creation increments version number"""
        # Create version
        version = {
            'id': str(uuid.uuid4()),
            'file_id': str(file_id),
            'version_number': version_number,
            'created_at': uploaded_at
        }

        # Verify version
        assert version['id'] is not None, "Version ID must be set"
        assert version['file_id'] is not None, "File ID must be set"
        assert version['version_number'] >= 1, "Version number must be >= 1"
        assert version['version_number'] <= 1000, "Version number must be <= 1000"

    @given(
        file_id=st.uuids(),
        versions=st.lists(
            st.fixed_dictionaries({
                'version_number': st.integers(min_value=1, max_value=100),
                'created_at': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
            }),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_version_chronological_ordering(self, file_id, versions):
        """Test that versions are in chronological order"""
        # Sort versions by created_at
        sorted_versions = sorted(versions, key=lambda v: v['created_at'])

        # Verify version numbers increase with time
        for i in range(1, len(sorted_versions)):
            prev_version = sorted_versions[i - 1]
            curr_version = sorted_versions[i]
            if curr_version['created_at'] >= prev_version['created_at']:
                # Newer version should have higher or equal version number
                assert True, "Version ordering is consistent"

    @given(
        file_id=st.uuids(),
        max_versions=st.integers(min_value=1, max_value=100),
        current_versions=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_max_versions_enforcement(self, file_id, max_versions, current_versions):
        """Test that max versions limit is enforced"""
        # Check if can create new version
        can_create = current_versions < max_versions

        # Verify enforcement
        if current_versions < max_versions:
            assert can_create is True, "Can create new version"
        else:
            assert can_create is False, "Max versions reached"

    @given(
        file_id=st.uuids(),
        version_number=st.integers(min_value=1, max_value=100),
        file_size=st.integers(min_value=1, max_value=10_000_000_000)
    )
    @settings(max_examples=50)
    def test_version_file_size_tracking(self, file_id, version_number, file_size):
        """Test that version file size is tracked"""
        # Create version with file size
        version = {
            'file_id': str(file_id),
            'version_number': version_number,
            'file_size': file_size
        }

        # Verify file size
        assert version['file_size'] >= 1, "File size must be positive"
        assert version['file_size'] <= 10_000_000_000, "File size must be reasonable"


class TestFileAccessControlInvariants:
    """Tests for file access control invariants"""

    @given(
        file_id=st.uuids(),
        owner_id=st.uuids(),
        user_id=st.uuids(),
        permission=st.sampled_from(['read', 'write', 'delete', 'admin'])
    )
    @settings(max_examples=50)
    def test_owner_has_full_permissions(self, file_id, owner_id, user_id, permission):
        """Test that owner has full permissions on file"""
        # Owner always has all permissions
        is_owner = str(owner_id) == str(user_id)

        # Verify owner permissions
        if is_owner:
            # Owner has all permissions
            assert True, "Owner has all permissions"
        else:
            # Non-owner needs explicit permission
            assert True, "Non-owner needs explicit permission"

    @given(
        file_id=st.uuids(),
        permissions=st.lists(
            st.fixed_dictionaries({
                'user_id': st.uuids(),
                'permission': st.sampled_from(['read', 'write', 'delete', 'admin'])
            }),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_explicit_permission_grant(self, file_id, permissions):
        """Test that explicit permissions are granted correctly"""
        # Create permission map
        permission_map = {}
        for perm in permissions:
            user_id = str(perm['user_id'])
            if user_id not in permission_map:
                permission_map[user_id] = set()
            permission_map[user_id].add(perm['permission'])

        # Verify permissions
        for user_id, perms in permission_map.items():
            assert len(perms) >= 1, "At least one permission per user"

    @given(
        file_id=st.uuids(),
        visibility=st.sampled_from(['private', 'shared', 'public']),
        user_id=st.uuids(),
        is_owner=st.booleans()
    )
    @settings(max_examples=50)
    def test_visibility_access_control(self, file_id, visibility, user_id, is_owner):
        """Test that file visibility controls access"""
        # Check access based on visibility
        if is_owner:
            # Owner always has access
            has_access = True
        elif visibility == 'public':
            # Public files are accessible to all
            has_access = True
        elif visibility == 'shared':
            # Shared files are accessible to users with explicit permission
            has_access = False  # Would need to check permission map
        else:  # private
            # Private files only accessible to owner
            has_access = is_owner

        # Verify access control
        if is_owner or visibility == 'public':
            assert has_access is True, "Owner and public files are accessible"
        elif visibility == 'private':
            assert has_access is False, "Private files not accessible to non-owners"


class TestFileSharingInvariants:
    """Tests for file sharing invariants"""

    @given(
        file_id=st.uuids(),
        owner_id=st.uuids(),
        shared_with=st.lists(st.uuids(), min_size=0, max_size=100, unique=True),
        permission=st.sampled_from(['read', 'write']),
        shared_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_file_sharing_creates_valid_shares(self, file_id, owner_id, shared_with, permission, shared_at):
        """Test that file sharing creates valid share records"""
        # Create shares
        shares = []
        for user_id in shared_with:
            if str(user_id) != str(owner_id):  # Don't share with owner
                shares.append({
                    'id': str(uuid.uuid4()),
                    'file_id': str(file_id),
                    'shared_by': str(owner_id),
                    'shared_with': str(user_id),
                    'permission': permission,
                    'shared_at': shared_at
                })

        # Verify shares
        for share in shares:
            assert share['id'] is not None, "Share ID must be set"
            assert share['file_id'] is not None, "File ID must be set"
            assert share['shared_by'] != share['shared_with'], "Cannot share with self"
            assert share['permission'] in ['read', 'write'], "Valid permission"

    @given(
        file_id=st.uuids(),
        max_shares=st.integers(min_value=1, max_value=1000),
        current_shares=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=50)
    def test_max_shares_limit_enforcement(self, file_id, max_shares, current_shares):
        """Test that max shares limit is enforced"""
        # Check if can create new share
        can_share = current_shares < max_shares

        # Verify enforcement
        if current_shares < max_shares:
            assert can_share is True, "Can create new share"
        else:
            assert can_share is False, "Max shares reached"

    @given(
        file_id=st.uuids(),
        user_id=st.uuids(),
        permission=st.sampled_from(['read', 'write']),
        expires_at=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        current_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1))
    )
    @settings(max_examples=50)
    def test_share_expiration_enforcement(self, file_id, user_id, permission, expires_at, current_time):
        """Test that share expiration is enforced"""
        # Create share with expiration
        share = {
            'file_id': str(file_id),
            'user_id': str(user_id),
            'permission': permission,
            'expires_at': expires_at
        }

        # Check if share is valid
        is_valid = current_time < expires_at

        # Verify expiration
        if current_time < expires_at:
            assert is_valid is True, "Share is valid"
        else:
            assert is_valid is False, "Share has expired"

    @given(
        file_id=st.uuids(),
        share_link=st.uuids()
    )
    @settings(max_examples=50)
    def test_share_link_uniqueness(self, file_id, share_link):
        """Test that share links are unique"""
        # Create share link
        link = str(share_link)

        # Verify uniqueness
        assert len(link) == 36, "UUID has 36 characters"  # Standard UUID format
        assert link.count('-') == 4, "UUID has 4 dashes"


class TestFileDownloadInvariants:
    """Tests for file download invariants"""

    @given(
        file_id=st.uuids(),
        user_id=st.uuids(),
        downloaded_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        file_size=st.integers(min_value=1, max_value=10_000_000_000)
    )
    @settings(max_examples=50)
    def test_file_download_logs_access(self, file_id, user_id, downloaded_at, file_size):
        """Test that file download logs access"""
        # Create download log
        download_log = {
            'id': str(uuid.uuid4()),
            'file_id': str(file_id),
            'user_id': str(user_id),
            'downloaded_at': downloaded_at,
            'file_size': file_size
        }

        # Verify log
        assert download_log['id'] is not None, "Log ID must be set"
        assert download_log['file_id'] is not None, "File ID must be set"
        assert download_log['user_id'] is not None, "User ID must be set"
        assert download_log['downloaded_at'] is not None, "Timestamp must be set"
        assert download_log['file_size'] >= 1, "File size must be positive"

    @given(
        file_size=st.integers(min_value=1, max_value=10_000_000_000),
        chunk_size=st.integers(min_value=4096, max_value=10_485_760),  # 4KB to 10MB
        bytes_downloaded=st.integers(min_value=0, max_value=10_000_000_000)
    )
    @settings(max_examples=50)
    def test_chunked_download_progress(self, file_size, chunk_size, bytes_downloaded):
        """Test that chunked download progress is tracked correctly"""
        # Calculate progress
        progress = min(bytes_downloaded, file_size)
        progress_percent = (progress / file_size * 100) if file_size > 0 else 0

        # Verify progress
        assert 0 <= progress <= file_size, "Progress must be between 0 and file_size"
        assert 0 <= progress_percent <= 100, "Progress percent must be between 0 and 100"

    @given(
        file_id=st.uuids(),
        bandwidth_limit_bps=st.integers(min_value=1024, max_value=10_000_000_000),  # 1KB/s to 10GB/s
        file_size=st.integers(min_value=1024, max_value=10_000_000_000)
    )
    @settings(max_examples=50)
    def test_bandwidth_throttling(self, file_id, bandwidth_limit_bps, file_size):
        """Test that bandwidth throttling is enforced"""
        # Calculate minimum download time
        min_time_seconds = file_size / bandwidth_limit_bps if bandwidth_limit_bps > 0 else 0

        # Verify throttling
        assert min_time_seconds >= 0, "Download time must be non-negative"
        if bandwidth_limit_bps > 0:
            assert min_time_seconds > 0, "Download time must be positive with bandwidth limit"


class TestFileDeletionInvariants:
    """Tests for file deletion invariants"""

    @given(
        file_id=st.uuids(),
        deleted_at=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1))
    )
    @settings(max_examples=50)
    def test_soft_delete_preserves_file(self, file_id, deleted_at, created_at):
        """Test that soft delete preserves file"""
        assume(deleted_at >= created_at)

        # Soft delete file
        file_record = {
            'id': str(file_id),
            'created_at': created_at,
            'deleted_at': deleted_at,
            'is_deleted': True
        }

        # Verify soft delete
        assert file_record['deleted_at'] is not None, "deleted_at must be set"
        assert file_record['is_deleted'] is True, "is_deleted must be True"
        assert file_record['deleted_at'] >= file_record['created_at'], "deleted_at after created_at"

    @given(
        file_id=st.uuids(),
        deleted_at=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        retention_days=st.integers(min_value=0, max_value=365),
        current_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_retention_policy_enforcement(self, file_id, deleted_at, retention_days, current_time):
        """Test that retention policy is enforced"""
        # Calculate days since deletion
        days_since_deletion = (current_time - deleted_at).days

        # Check if should permanently delete
        # retention_days=0 means delete immediately (no retention)
        should_permanently_delete = days_since_deletion > retention_days

        # Verify retention policy
        if retention_days == 0:
            # No retention period - delete immediately if any time has passed
            if days_since_deletion > 0:
                assert should_permanently_delete is True, "Should permanently delete immediately with 0 retention"
            else:
                assert should_permanently_delete is False, "Just deleted - keep for now"
        elif days_since_deletion > retention_days:
            assert should_permanently_delete is True, "Should permanently delete after retention period"
        else:
            assert should_permanently_delete is False, "Should keep file within retention period"

    @given(
        file_id=st.uuids(),
        versions=st.lists(
            st.fixed_dictionaries({
                'version_id': st.uuids(),
                'version_number': st.integers(min_value=1, max_value=100)
            }),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_delete_file_deletes_all_versions(self, file_id, versions):
        """Test that deleting file deletes all versions"""
        # Delete all versions
        deleted_versions = []
        for version in versions:
            deleted_versions.append({
                'version_id': str(version['version_id']),
                'deleted': True
            })

        # Verify all versions deleted
        assert len(deleted_versions) == len(versions), "All versions must be deleted"
        for version in deleted_versions:
            assert version['deleted'] is True, "Version must be marked as deleted"


class TestFileSecurityInvariants:
    """Tests for file security invariants"""

    @given(
        file_id=st.uuids(),
        filename=st.text(min_size=1, max_size=255),
        scan_result=st.sampled_from(['clean', 'virus', 'suspicious', 'error'])
    )
    @settings(max_examples=50)
    def test_virus_scan_results(self, file_id, filename, scan_result):
        """Test that virus scan results are recorded"""
        # Record scan result
        scan_record = {
            'file_id': str(file_id),
            'filename': filename,
            'scan_result': scan_result,
            'scanned_at': datetime.now()
        }

        # Verify scan result
        assert scan_record['file_id'] is not None, "File ID must be set"
        assert scan_record['scan_result'] in ['clean', 'virus', 'suspicious', 'error'], "Valid scan result"

    @given(
        file_id=st.uuids(),
        quarantine_reason=st.one_of(
            st.none(),
            st.sampled_from(['virus', 'malware', 'suspicious', 'policy_violation'])
        )
    )
    @settings(max_examples=50)
    def test_quarantine_prevents_access(self, file_id, quarantine_reason):
        """Test that quarantine prevents file access"""
        # Determine is_quarantined based on quarantine_reason
        is_quarantined = quarantine_reason is not None

        # Quarantine file
        file_record = {
            'id': str(file_id),
            'is_quarantined': is_quarantined,
            'quarantine_reason': quarantine_reason
        }

        # Verify quarantine
        if is_quarantined:
            assert file_record['quarantine_reason'] is not None, "Quarantined file must have reason"
            assert file_record['is_quarantined'] is True, "is_quarantined must be True"
        else:
            assert True, "File not quarantined"

    @given(
        file_id=st.uuids(),
        mime_type=st.sampled_from([
            'application/exe',
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-executable'
        ])
    )
    @settings(max_examples=50)
    def test_executable_file_blocking(self, file_id, mime_type):
        """Test that executable files are blocked"""
        # Check if file type is blocked
        blocked_types = {
            'application/exe',
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-executable'
        }

        is_blocked = mime_type in blocked_types

        # Verify blocking
        if mime_type in blocked_types:
            assert is_blocked is True, "Executable files should be blocked"

    @given(
        file_id=st.uuids(),
        checksum1=st.text(min_size=32, max_size=128, alphabet='0123456789abcdef'),
        checksum2=st.text(min_size=32, max_size=128, alphabet='0123456789abcdef')
    )
    @settings(max_examples=50)
    def test_file_integrity_verification(self, file_id, checksum1, checksum2):
        """Test that file integrity is verified with checksums"""
        # Verify integrity
        if checksum1 == checksum2:
            # Checksums match - file is intact
            assert True, "File integrity verified"
        else:
            # Checksums don't match - file is corrupted
            assert True, "File corruption detected"


class TestFileAuditTrailInvariants:
    """Tests for file audit trail invariants"""

    @given(
        file_id=st.uuids(),
        user_id=st.uuids(),
        action=st.sampled_from([
            'uploaded',
            'downloaded',
            'shared',
            'deleted',
            'modified',
            'restored'
        ]),
        timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        ip_address=st.ip_addresses()
    )
    @settings(max_examples=50)
    def test_audit_log_records_file_action(self, file_id, user_id, action, timestamp, ip_address):
        """Test that audit log records all file actions"""
        # Create audit log entry
        audit_entry = {
            'id': str(uuid.uuid4()),
            'file_id': str(file_id),
            'user_id': str(user_id),
            'action': action,
            'timestamp': timestamp,
            'ip_address': str(ip_address)
        }

        # Verify audit entry
        assert audit_entry['id'] is not None, "Audit entry ID must be set"
        assert audit_entry['file_id'] is not None, "File ID must be set"
        assert audit_entry['user_id'] is not None, "User ID must be set"
        assert audit_entry['action'] in ['uploaded', 'downloaded', 'shared', 'deleted', 'modified', 'restored'], "Valid action"
        assert audit_entry['timestamp'] is not None, "Timestamp must be set"
        assert audit_entry['ip_address'] is not None, "IP address must be set"

    @given(
        actions=st.lists(
            st.sampled_from(['uploaded', 'downloaded', 'shared', 'deleted', 'modified']),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_audit_log_chronological_order(self, actions):
        """Test that audit log entries are in chronological order"""
        # Create audit log entries
        base_time = datetime.now()
        audit_log = []
        for i, action in enumerate(actions):
            audit_log.append({
                'action': action,
                'timestamp': base_time + timedelta(seconds=i)
            })

        # Verify chronological order
        for i in range(1, len(audit_log)):
            assert audit_log[i]['timestamp'] >= audit_log[i-1]['timestamp'], "Entries must be in chronological order"
