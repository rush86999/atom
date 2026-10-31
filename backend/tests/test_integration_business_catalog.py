"""The public business-integration catalog must be truthful and >= 46."""
from core.integration_business_catalog import build_business_catalog


def test_catalog_meets_readme_threshold():
    catalog = build_business_catalog()
    assert catalog["total"] >= 46, catalog["by_category"]
    assert len(catalog["providers"]) == catalog["total"]


def test_every_provider_carries_resolvable_evidence():
    catalog = build_business_catalog()
    allowed = {"oauth", "adapter", "routes", "env_key", "connection"}
    for provider in catalog["providers"]:
        assert provider["evidence"], provider
        assert set(provider["evidence"]) <= allowed, provider
        assert provider["id"] and provider["name"] and provider["category"]


def test_aliases_are_not_double_counted():
    catalog = build_business_catalog()
    ids = [p["id"] for p in catalog["providers"]]
    assert len(ids) == len(set(ids))
    assert "gdrive" not in ids and "google_drive" in ids
    assert "microsoft" not in ids and "microsoft365" in ids
    assert "zoho-books" not in ids and "zoho_books" in ids


def test_named_readme_providers_are_present():
    ids = {p["id"] for p in build_business_catalog()["providers"]}
    for required in (
        "salesforce", "hubspot", "slack", "teams", "gmail", "notion",
        "jira", "linear", "stripe", "quickbooks", "shopify", "github",
        "gitlab", "zoom",
    ):
        assert required in ids, required
