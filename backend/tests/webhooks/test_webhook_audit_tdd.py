from __future__ import annotations

"""
TDD Tests for Webhook Integration Audit Scanner (Task 1)

Tests the integration audit scanner that discovers webhook endpoints,
validates transformer format compliance, and generates rollout reports.

Test Categories:
1. Scanner discovers all integrations from api/routes/integrations/
2. Scanner detects existing webhook endpoints in ingestion_webhooks.py
3. Scanner identifies transformers in IngestionPipelineService
4. Scanner validates transformer format compliance
5. Scanner generates JSON, CSV, and Markdown reports
6. Scanner calculates rollout priority based on business value
"""

import json
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the scanner we're testing
from scripts.audit_webhook_integrations import (
    WebhookAuditScanner,
    WebhookAuditMetrics,
    WebhookAuditSummary,
    calculate_rollout_priority,
    get_provider_category,
    TRANSFORMER_REQUIRED_FIELDS,
)


@pytest.fixture
def mock_integrations_dir(tmp_path):
    """Create a mock integrations directory with test files."""
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()

    # Create mock integration files
    (integrations_dir / "slack_routes.py").write_text("""
@router.post("/webhooks/slack/events")
async def slack_webhook_handler():
    pass
""")

    (integrations_dir / "hubspot_routes.py").write_text("""
@router.post("/webhooks/hubspot/events")
async def hubspot_webhook_handler():
    pass
""")

    (integrations_dir / "asana_routes.py").write_text("""
# Asana integration routes
@router.get("/asana/sync")
async def asana_sync():
    pass
""")

    (integrations_dir / "__init__.py").write_text("")

    return integrations_dir


@pytest.fixture
def mock_webhooks_file(tmp_path):
    """Create a mock webhooks ingestion file."""
    webhooks_file = tmp_path / "ingestion_webhooks.py"
    webhooks_file.write_text("""
@router.post("/webhooks/slack/events")
async def slack_webhook_handler():
    pass

@router.post("/webhooks/hubspot/events")
async def hubspot_webhook_handler():
    pass

@router.post("/webhooks/outlook/events")
async def outlook_webhook_handler():
    pass
""")
    return webhooks_file


@pytest.fixture
def mock_pipeline_file(tmp_path):
    """Create a mock ingestion pipeline file with transformers."""
    pipeline_file = tmp_path / "ingestion_pipeline.py"
    pipeline_file.write_text("""
class IngestionPipelineService:
    async def _transform_slack_payload(self, webhook_data):
        return [
            {
                "id": "msg123",
                "sender_id": "U123",
                "subject": "Test Message",
                "content": "Test content",
                "timestamp": "2024-01-01T00:00:00Z",
                "metadata": {"source": "slack"}
            }
        ]

    async def _transform_hubspot_payload(self, webhook_data):
        return [
            {
                "id": "contact123",
                "sender_id": "hubspot_user",
                "subject": "Contact Created",
                "content": "Contact data",
                "timestamp": "2024-01-01T00:00:00Z",
                "metadata": {"source": "hubspot"}
            }
        ]

    async def _transform_asana_payload(self, webhook_data):
        # Missing required fields - non-compliant
        return [
            {
                "raw": "asana raw data"
            }
        ]
""")

    # Create transformer map
    return pipeline_file


class TestScannerDiscoversAllIntegrations:
    """Test 1: Scanner discovers all integrations from api/routes/integrations/"""

    def test_scanner_discovers_integration_files(self, mock_integrations_dir):
        """Scanner finds all Python integration files."""
        scanner = WebhookAuditScanner(integrations_dir=mock_integrations_dir)

        integrations = scanner._discover_integrations()

        assert len(integrations) == 3
        assert "slack" in [i["provider_id"] for i in integrations]
        assert "hubspot" in [i["provider_id"] for i in integrations]
        assert "asana" in [i["provider_id"] for i in integrations]

    def test_scanner_excludes_init_files(self, tmp_path):
        """Scanner excludes __init__.py from results."""
        integrations_dir = tmp_path / "integrations"
        integrations_dir.mkdir()
        (integrations_dir / "__init__.py").write_text("")
        (integrations_dir / "slack_routes.py").write_text("")

        scanner = WebhookAuditScanner(integrations_dir=integrations_dir)
        integrations = scanner._discover_integrations()

        assert len(integrations) == 1
        assert integrations[0]["provider_id"] == "slack"

    def test_scanner_handles_empty_directory(self, tmp_path):
        """Scanner handles empty integrations directory."""
        integrations_dir = tmp_path / "integrations"
        integrations_dir.mkdir()

        scanner = WebhookAuditScanner(integrations_dir=integrations_dir)
        integrations = scanner._discover_integrations()

        assert len(integrations) == 0


class TestScannerDetectsWebhookEndpoints:
    """Test 2: Scanner detects existing webhook endpoints in ingestion_webhooks.py"""

    def test_scanner_parses_webhook_routes(self, mock_integrations_dir):
        """Scanner correctly parses webhook route patterns."""
        scanner = WebhookAuditScanner(integrations_dir=mock_integrations_dir)

        # Mock webhooks content
        webhooks_content = """
@router.post("/webhooks/slack/events")
async def slack_webhook_handler():
    pass

@router.post("/webhooks/salesforce/events")
async def salesforce_webhook_handler():
    pass

@router.post("/webhooks/gmail/events")
async def gmail_webhook_handler():
    pass
"""

        detected = scanner._parse_webhook_routes(webhooks_content)

        assert "slack" in detected
        assert "salesforce" in detected
        assert "gmail" in detected

    def test_scanner_detects_zoho_suite_webhooks(self):
        """Scanner detects Zoho suite webhook handlers."""
        scanner = WebhookAuditScanner(integrations_dir=Path("/tmp"))

        webhooks_content = """
ZOHO_INTEGRATIONS = {
    "zoho_crm",
    "zoho_books",
    "zoho_projects",
}

@router.post("/webhooks/zoho/{integration_id}")
async def zoho_webhook_handler():
    pass
"""

        detected = scanner._parse_webhook_routes(webhooks_content)

        assert "zoho_crm" in detected
        assert "zoho_books" in detected
        assert "zoho_projects" in detected


class TestScannerIdentifiesTransformers:
    """Test 3: Scanner identifies transformers in IngestionPipelineService"""

    def test_scanner_normalizes_provider_names(self):
        """Scanner correctly normalizes provider names from various formats."""
        scanner = WebhookAuditScanner(integrations_dir=Path("/tmp"))

        method_names = [
            "_transform_slack_payload",
            "_transform_hubspot_payload",
            "_transform_microsoft365_payload",
            "_transform_gmail_payload",
        ]

        mapped = [scanner._normalize_provider_name(name) for name in method_names]

        assert "slack" in mapped
        assert "hubspot" in mapped
        assert "microsoft365" in mapped
        assert "gmail" in mapped

    def test_scanner_normalizes_routes_filenames(self):
        """Scanner normalizes provider names from route file names."""
        scanner = WebhookAuditScanner(integrations_dir=Path("/tmp"))

        filenames = [
            "slack_routes.py",
            "hubspot_routes.py",
            "microsoft365_routes.py",
            "zoho_crm_routes.py",
        ]

        mapped = [scanner._extract_provider_id(Path(f)) for f in filenames]

        assert "slack" in mapped
        assert "hubspot" in mapped
        assert "microsoft365" in mapped
        assert "zoho-crm" in mapped


class TestScannerValidatesTransformerFormat:
    """Test 4: Scanner validates transformer format compliance"""

    def test_scanner_validates_compliant_transformer(self):
        """Scanner recognizes compliant transformer format."""
        compliant_record = {
            "id": "msg123",
            "sender_id": "U123",
            "subject": "Test",
            "content": "Test content",
            "timestamp": "2024-01-01T00:00:00Z",
            "metadata": {"source": "test"}
        }

        is_compliant = WebhookAuditScanner._validate_record_format(compliant_record)
        assert is_compliant is True

    def test_scanner_detects_missing_fields(self):
        """Scanner detects missing required fields."""
        non_compliant_record = {
            "id": "msg123",
            "raw": "some raw data"  # Missing standard fields
        }

        is_compliant = WebhookAuditScanner._validate_record_format(non_compliant_record)
        assert is_compliant is False

    def test_scanner_gets_missing_fields(self):
        """Scanner returns list of missing fields."""
        required_fields = ["id", "sender_id", "subject", "content", "timestamp", "metadata"]

        # Missing sender_id and content
        incomplete_record = {
            "id": "msg123",
            "subject": "Test",
            "timestamp": "2024-01-01T00:00:00Z",
            "metadata": {},
        }

        missing = WebhookAuditScanner._get_missing_fields(incomplete_record)
        assert "sender_id" in missing
        assert "content" in missing
        assert len(missing) == 2

    def test_scanner_checks_all_required_fields(self):
        """Scanner validates all required fields are present."""
        # Test each missing field
        required_fields = ["id", "sender_id", "subject", "content", "timestamp", "metadata"]

        for field in required_fields:
            incomplete_record = {
                f: f"value_{f}" for f in required_fields if f != field
            }
            is_compliant = WebhookAuditScanner._validate_record_format(incomplete_record)
            assert is_compliant is False, f"Should fail when {field} is missing"


class TestScannerGeneratesReports:
    """Test 5: Scanner generates JSON, CSV, and Markdown reports"""

    def test_scanner_generates_json_report(self, tmp_path):
        """Scanner generates JSON report with all audit data."""
        scanner = WebhookAuditScanner(integrations_dir=Path("/tmp"))

        # Create mock audit results
        scanner.audits = [
            WebhookAuditMetrics(
                provider_name="Slack",
                provider_id="slack",
                category="messaging",
                webhook_ready=True,
                has_transformer=True,
                transformer_compliant=True,
                oauth_supported=True,
                subscription_api="full",
                business_priority=1,
                rollout_tier=1,
                transformers_count=1,
                missing_fields=[],
            )
        ]

        summary = scanner._generate_summary()
        json_path = tmp_path / "audit_results.json"

        from scripts.audit_webhook_integrations import generate_json_report
        generate_json_report(summary, json_path)

        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert "summary" in data
        assert "audits" in data
        assert len(data["audits"]) == 1
        assert data["audits"][0]["provider_name"] == "Slack"

    def test_scanner_generates_csv_report(self, tmp_path):
        """Scanner generates CSV report for spreadsheet analysis."""
        scanner = WebhookAuditScanner(integrations_dir=Path("/tmp"))

        scanner.audits = [
            WebhookAuditMetrics(
                provider_name="Slack",
                provider_id="slack",
                category="messaging",
                webhook_ready=True,
                has_transformer=True,
                transformer_compliant=True,
                oauth_supported=True,
                subscription_api="full",
                business_priority=1,
                rollout_tier=1,
                transformers_count=1,
                missing_fields=[],
            )
        ]

        summary = scanner._generate_summary()
        csv_path = tmp_path / "audit_report.csv"

        from scripts.audit_webhook_integrations import generate_csv_report
        generate_csv_report(summary, csv_path)

        assert csv_path.exists()

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["Provider"] == "Slack"
        assert rows[0]["Category"] == "messaging"

    def test_scanner_generates_markdown_report(self, tmp_path):
        """Scanner generates human-readable Markdown summary."""
        scanner = WebhookAuditScanner(integrations_dir=Path("/tmp"))

        scanner.audits = [
            WebhookAuditMetrics(
                provider_name="Slack",
                provider_id="slack",
                category="messaging",
                webhook_ready=True,
                has_transformer=True,
                transformer_compliant=True,
                oauth_supported=True,
                subscription_api="full",
                business_priority=1,
                rollout_tier=1,
                transformers_count=1,
                missing_fields=[],
            )
        ]

        summary = scanner._generate_summary()
        md_path = tmp_path / "audit_summary.md"

        from scripts.audit_webhook_integrations import generate_markdown_report
        generate_markdown_report(summary, md_path)

        assert md_path.exists()

        content = md_path.read_text()
        assert "# Webhook Integration Audit Report" in content
        assert "Slack" in content
        assert "## Rollout Tiers" in content


class TestScannerPrioritizesByBusinessValue:
    """Test 6: Scanner calculates rollout priority based on business value"""

    def test_messaging_has_highest_priority(self):
        """Messaging integrations have highest priority (1)."""
        assert get_provider_category("slack") == "messaging"
        assert get_provider_category("discord") == "messaging"
        assert get_provider_category("whatsapp") == "messaging"

    def test_crm_has_second_priority(self):
        """CRM integrations have second priority (2)."""
        assert get_provider_category("salesforce") == "crm"
        assert get_provider_category("hubspot") == "crm"
        assert get_provider_category("pipedrive") == "crm"

    def test_productivity_has_third_priority(self):
        """Productivity integrations have third priority (3)."""
        assert get_provider_category("google") == "productivity"
        assert get_provider_category("notion") == "productivity"
        assert get_provider_category("asana") == "productivity"

    def test_rollout_tier_calculation(self):
        """Rollout tier is calculated based on webhook readiness."""
        # Tier 1: Has webhook + transformer
        tier1 = calculate_rollout_priority(
            webhook_ready=True,
            has_transformer=True,
            transformer_compliant=True,
        )
        assert tier1 == 1

        # Tier 2: Has transformer but no webhook
        tier2 = calculate_rollout_priority(
            webhook_ready=False,
            has_transformer=True,
            transformer_compliant=True,
        )
        assert tier2 == 2

        # Tier 3: Has webhook but transformer needs fixing
        tier3 = calculate_rollout_priority(
            webhook_ready=True,
            has_transformer=True,
            transformer_compliant=False,
        )
        assert tier3 == 3

        # Tier 4: No webhook, no transformer
        tier4 = calculate_rollout_priority(
            webhook_ready=False,
            has_transformer=False,
            transformer_compliant=False,
        )
        assert tier4 == 4


class TestScannerIntegration:
    """Integration tests for the complete scanner workflow."""

    def test_end_to_end_scan(self, mock_integrations_dir):
        """Scanner runs complete scan and generates all reports."""
        scanner = WebhookAuditScanner(integrations_dir=mock_integrations_dir)

        summary = scanner.scan_all()

        assert summary.total_integrations > 0
        assert summary.audits is not None

    def test_summary_calculates_metrics(self, mock_integrations_dir):
        """Scanner summary correctly calculates rollout metrics."""
        scanner = WebhookAuditScanner(integrations_dir=mock_integrations_dir)

        # Add mock audits
        scanner.audits = [
            WebhookAuditMetrics(
                provider_name="Slack",
                provider_id="slack",
                category="messaging",
                webhook_ready=True,
                has_transformer=True,
                transformer_compliant=True,
                oauth_supported=True,
                subscription_api="full",
                business_priority=1,
                rollout_tier=1,
                transformers_count=1,
                missing_fields=[],
            ),
            WebhookAuditMetrics(
                provider_name="Asana",
                provider_id="asana",
                category="productivity",
                webhook_ready=False,
                has_transformer=True,
                transformer_compliant=False,
                oauth_supported=True,
                subscription_api="partial",
                business_priority=3,
                rollout_tier=2,
                transformers_count=1,
                missing_fields=["id", "subject"],
            ),
        ]

        summary = scanner._generate_summary()

        assert summary.total_integrations == 2
        assert summary.webhook_ready_count == 1
        assert summary.transformer_compliant_count == 1


class TestTransformerRequiredFields:
    """Test transformer required fields constant."""

    def test_required_fields_defined(self):
        """TRANSFORMER_REQUIRED_FIELDS includes all expected fields."""
        expected = {"id", "sender_id", "subject", "content", "timestamp", "metadata"}
        assert set(TRANSFORMER_REQUIRED_FIELDS) == expected

    def test_field_validation(self):
        """Validator checks all required fields."""
        record = {
            "id": "test",
            "sender_id": "sender",
            "subject": "subject",
            "content": "content",
            "timestamp": "2024-01-01T00:00:00Z",
            "metadata": {},
        }

        missing = WebhookAuditScanner._get_missing_fields(record)
        assert len(missing) == 0
