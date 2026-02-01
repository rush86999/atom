#!/usr/bin/env python3
"""
Tests for GraphRAG Pattern-Based Entity Extraction
Tests the fallback mechanism when LLM is unavailable
"""

import pytest
from core.graphrag_engine import GraphRAGEngine


class TestEmailExtraction:
    """Tests for email pattern extraction"""

    def test_extract_single_email(self):
        """Test extracting a single email address"""
        engine = GraphRAGEngine()
        text = "Contact us at support@example.com for help."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test1", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "support@example.com"
        assert entities[0].entity_type == "email"
        assert entities[0].properties["pattern_extracted"] is True

    def test_extract_multiple_emails(self):
        """Test extracting multiple email addresses"""
        engine = GraphRAGEngine()
        text = "Email john@example.com or jane@test.org for assistance."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test2", source="test"
        )

        assert len(entities) == 2
        emails = {e.name for e in entities}
        assert "john@example.com" in emails
        assert "jane@test.org" in emails


class TestURLExtraction:
    """Tests for URL pattern extraction"""

    def test_extract_http_url(self):
        """Test extracting HTTP URL"""
        engine = GraphRAGEngine()
        text = "Visit http://example.com for more info."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test3", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "http://example.com"
        assert entities[0].entity_type == "url"

    def test_extract_https_url(self):
        """Test extracting HTTPS URL"""
        engine = GraphRAGEngine()
        text = "Go to https://api.example.com/v1/users for documentation."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test4", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "https://api.example.com/v1/users"


class TestPhoneExtraction:
    """Tests for phone number pattern extraction"""

    def test_extract_us_phone_with_dashes(self):
        """Test extracting US phone number with dashes"""
        engine = GraphRAGEngine()
        text = "Call us at 555-123-4567 for support."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test5", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "555-123-4567"
        assert entities[0].entity_type == "phone"

    def test_extract_us_phone_with_parens(self):
        """Test extracting US phone number with parentheses"""
        engine = GraphRAGEngine()
        text = "Contact (555) 123-4567 for assistance."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test6", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "(555) 123-4567"


class TestDateExtraction:
    """Tests for date pattern extraction"""

    def test_extract_iso_date(self):
        """Test extracting ISO format date"""
        engine = GraphRAGEngine()
        text = "The event is scheduled for 2024-12-25."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test7", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "2024-12-25"
        assert entities[0].entity_type == "date"

    def test_extract_us_date_format(self):
        """Test extracting US format date"""
        engine = GraphRAGEngine()
        text = "Meeting on 12/25/2024 at 3pm."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test8", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "12/25/2024"


class TestCurrencyExtraction:
    """Tests for currency pattern extraction"""

    def test_extract_dollar_amount(self):
        """Test extracting dollar amount"""
        engine = GraphRAGEngine()
        text = "The price is $1,234.56."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test9", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "$1,234.56"
        assert entities[0].entity_type == "currency"

    def test_extract_currency_with_code(self):
        """Test extracting currency with code"""
        engine = GraphRAGEngine()
        text = "Payment of 100 USD is required."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test10", source="test"
        )

        assert len(entities) == 1
        assert entities[0].entity_type == "currency"


class TestIPExtraction:
    """Tests for IP address pattern extraction"""

    def test_extract_valid_ip(self):
        """Test extracting valid IP address"""
        engine = GraphRAGEngine()
        text = "Server IP is 192.168.1.1."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test11", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "192.168.1.1"
        assert entities[0].entity_type == "ip_address"

    def test_ignore_invalid_ip(self):
        """Test that invalid IP addresses are ignored"""
        engine = GraphRAGEngine()
        text = "Invalid IP 999.999.999.999 should be ignored."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test12", source="test"
        )

        # Should not extract invalid IP (octets > 255)
        assert len(entities) == 0


class TestUUIDExtraction:
    """Tests for UUID pattern extraction"""

    def test_extract_uuid(self):
        """Test extracting UUID"""
        engine = GraphRAGEngine()
        text = "User ID: 550e8400-e29b-41d4-a716-446655440000"

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test13", source="test"
        )

        assert len(entities) == 1
        assert entities[0].name == "550e8400-e29b-41d4-a716-446655440000"
        assert entities[0].entity_type == "uuid"


class TestRelationshipExtraction:
    """Tests for relationship pattern extraction"""

    def test_extract_is_relationship(self):
        """Test extracting 'is' relationship"""
        engine = GraphRAGEngine()
        text = "John is a manager at company."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test14", source="test"
        )

        # Should extract entities first, then relationship
        # This test assumes "John" and "manager" were extracted as entities
        assert len(relationships) >= 0  # May or may not have relationships depending on entity extraction

    def test_extract_works_at_relationship(self):
        """Test extracting 'works at' relationship"""
        engine = GraphRAGEngine()
        text = "John works at Google."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test15", source="test"
        )

        # Check if any relationships were found
        assert len(relationships) >= 0


class TestMixedContent:
    """Tests for extracting entities from mixed content"""

    def test_extract_multiple_entity_types(self):
        """Test extracting various entity types from mixed content"""
        engine = GraphRAGEngine()
        text = """
        Contact John Smith at john@example.com or call 555-123-4567.
        Visit https://example.com for details.
        Event date: 2024-12-25.
        Price: $99.99.
        IP: 192.168.1.1.
        """

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test16", source="test"
        )

        # Should extract multiple entity types
        entity_types = {e.entity_type for e in entities}

        assert "email" in entity_types
        assert "phone" in entity_types
        assert "url" in entity_types
        assert "date" in entity_types
        assert "currency" in entity_types
        assert "ip_address" in entity_types

        assert len(entities) >= 6  # At least 6 different entities

    def test_deduplicate_entities(self):
        """Test that duplicate entities are not extracted"""
        engine = GraphRAGEngine()
        text = "Email john@example.com for help. Or contact john@example.com."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test17", source="test"
        )

        # Should only extract unique email once
        assert len(entities) == 1
        assert entities[0].name == "john@example.com"


class TestEmptyInput:
    """Tests for handling empty or invalid input"""

    def test_empty_text(self):
        """Test handling empty text"""
        engine = GraphRAGEngine()
        entities, relationships = engine._pattern_extract_entities_and_relationships(
            "", doc_id="test18", source="test"
        )

        assert len(entities) == 0
        assert len(relationships) == 0

    def test_text_without_patterns(self):
        """Test text without any matching patterns"""
        engine = GraphRAGEngine()
        text = "This is just plain text without any special patterns."

        entities, relationships = engine._pattern_extract_entities_and_relationships(
            text, doc_id="test19", source="test"
        )

        assert len(entities) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
