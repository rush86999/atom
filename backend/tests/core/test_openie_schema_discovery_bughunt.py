# -*- coding: utf-8 -*-
"""Bug-hunt tests (TDD RED->GREEN) for core/openie_schema_discovery.py.

Each test targets a genuinely-new bug (fix absent from HEAD).
"""
import pytest

from core.openie_schema_discovery import OpenIESchemaDiscovery


# ============================================================================
# BUG 1 (HIGH): _normalize_slug mishandles "-ies" plurals, producing malformed
# singulars and breaking slug deduplication.
#
# Words ending in "-ies" are plurals of "-y" nouns (country->countries,
# query->queries, category->categories, property->properties). The generic
# plural rule blindly strips the trailing "s", yielding "countrie", "querie",
# "categorie", "propertie" — malformed tokens that:
#   (a) don't match the intended singular, and
#   (b) deduplicate DIFFERENTLY from the correct singular.
# This means LLM-discovered "countries" and "country" become two separate
# entity-type slugs, defeating the entire dedup purpose of the normalizer.
#
# Also affects invariants like "series" (already singular) which becomes
# the bogus "serie".
# ============================================================================


class TestNormalizeSlugIesPlurals:
    """BUG: -ies plurals must singularize to -y, not strip just the 's'."""

    @pytest.mark.parametrize(
        "plural,singular",
        [
            ("countries", "country"),
            ("queries", "query"),
            ("categories", "category"),
            ("properties", "property"),
            ("companies", "company"),  # note: also in PLURAL_TO_SINGULAR map
            ("stories", "story"),
            ("libraries", "library"),
            ("memories", "memory"),
            ("inventories", "inventory"),
            ("histories", "history"),
        ],
    )
    def test_ies_plural_singularizes_to_y(self, plural, singular):
        """BUG: 'countries' must normalize to 'country', not 'countrie'."""
        result = OpenIESchemaDiscovery._normalize_slug(plural)
        assert result == singular, (
            f"_normalize_slug({plural!r}) returned {result!r}, expected {singular!r}"
        )

    def test_series_stays_singular(self):
        """BUG: 'series' is invariant (singular==plural) — must not become 'serie'."""
        result = OpenIESchemaDiscovery._normalize_slug("series")
        assert result == "series", f"_normalize_slug('series') -> {result!r}"

    def test_dedup_consistency_plural_vs_singular(self):
        """BUG: plural and singular must normalize to the SAME slug (dedup invariant)."""
        # If 'countries' and 'country' normalize differently, the normalizer
        # fails its core purpose of deduplicating near-identical LLM slugs.
        from_plural = OpenIESchemaDiscovery._normalize_slug("countries")
        from_singular = OpenIESchemaDiscovery._normalize_slug("country")
        assert from_plural == from_singular, (
            f"dedup broken: 'countries'->{from_plural!r} != 'country'->{from_singular!r}"
        )


# Regression guards for behavior that must NOT change ---------------------------------


class TestNormalizeSlugRegression:
    """Ensure existing correct behavior is preserved after the fix."""

    @pytest.mark.parametrize(
        "slug,expected",
        [
            ("emails", "email"),
            ("tasks", "task"),
            ("status", "status"),       # ends in 'us', not stripped
            ("address", "address"),     # ends in 'ss', not stripped
            ("data", "data"),           # len 4, not > 4
            ("analysis", "analysis"),   # ends in 'is', not stripped
            ("email_subject", "email"), # alias map
            ("people", "person"),       # alias map
        ],
    )
    def test_existing_behavior_preserved(self, slug, expected):
        assert OpenIESchemaDiscovery._normalize_slug(slug) == expected
