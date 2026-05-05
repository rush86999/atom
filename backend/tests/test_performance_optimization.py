"""
Performance Optimization Tests

Tests for batch processing, prompt caching, and model selection features.
Phase 323-03: Performance Optimization
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from core.multi_entity_llm_extractor import MultiEntityLLMExtractor
from core.models import DiscoveredEntity


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def extractor():
    """MultiEntityLLMExtractor instance with optimizations enabled."""
    return MultiEntityLLMExtractor(
        enable_prompt_caching=True,
        enable_model_selection=True
    )


@pytest.fixture
def sample_emails():
    """Sample emails for batch processing."""
    return [
        {
            "id": f"email-{i:03d}",
            "subject": f"Test Email {i}",
            "from": f"sender{i}@example.com",
            "to": ["recipient@example.com"],
            "body": f"This is test email {i} with some content."
        }
        for i in range(1, 51)  # 50 emails
    ]


@pytest.fixture
def simple_email():
    """Simple email (<100 words)."""
    return {
        "id": "email-simple",
        "subject": "Quick Question",
        "from": "user@example.com",
        "to": ["support@example.com"],
        "body": "Hi, I have a quick question about my account. Can you help?"
    }


@pytest.fixture
def complex_email():
    """Complex email (>200 words, complex keywords)."""
    return {
        "id": "email-complex",
        "subject": "Legal Contract Review - Technical Specifications",
        "from": "legal@company.com",
        "to": ["engineering@company.com", "management@company.com"],
        "cc": ["counsel@firm.com"],
        "attachments": ["contract_v2.pdf", "specifications.docx"],
        "body": """
        This email contains a comprehensive legal contract review with detailed technical specifications.
        The contract outlines liability provisions, financial forecasts, and revenue projections.
        Technical architecture integration points are documented in the attached specifications.
        Please review the integration architecture and provide feedback on the technical implementation.
        Financial terms include budget allocations and revenue sharing agreements.
        """
    }


@pytest.fixture
def po_emails():
    """Purchase order emails for caching tests."""
    return [
        {
            "id": f"po-{i}",
            "subject": f"Purchase Order PO-100{i} Approved",
            "from": f"vendor{i}@acme.com",
            "to": ["admin@company.com"],
            "body": f"Please approve purchase order PO-100{i} for $1,000."
        }
        for i in range(10)
    ]


# ============================================================================
# Test Class 1: Batch Processing
# ============================================================================

class TestBatchProcessing:
    """Tests for batch extraction performance."""

    @pytest.mark.asyncio
    async def test_extract_batch_processes_50_emails(self, extractor, sample_emails):
        """Test batch processing handles 50 emails."""
        # Act
        entities = await extractor.extract_batch(
            sample_emails,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            batch_id="batch-test"
        )

        # Assert
        assert len(entities) >= 50  # At least 1 entity per email
        assert all(e.batch_id == "batch-test" for e in entities)
        assert len(set(e.source_record_id for e in entities)) == 50  # All emails represented

    @pytest.mark.asyncio
    async def test_extract_batch_empty_list(self, extractor):
        """Test batch processing handles empty list."""
        # Act
        entities = await extractor.extract_batch(
            [],
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_extract_batch_uses_parallel_processing(self, extractor, sample_emails):
        """Test that batch processing uses parallel execution."""
        # Mock the extract_from_email to track parallel calls
        call_count = 0
        call_lock = asyncio.Lock()

        original_extract = extractor.extract_from_email

        async def tracked_extract(*args, **kwargs):
            nonlocal call_count
            async with call_lock:
                call_count += 1
            # Simulate processing delay
            await asyncio.sleep(0.01)
            return []

        extractor.extract_from_email = tracked_extract

        # Act - Process 50 emails
        start_time = datetime.now(timezone.utc)
        entities = await extractor.extract_batch(
            sample_emails[:20],  # 20 emails
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )
        end_time = datetime.now(timezone.utc)

        # Assert - Parallel execution should be faster than sequential
        # Sequential: 20 * 0.01s = 0.2s
        # Parallel (batch size 10): 2 * 0.01s = 0.02s
        duration_ms = (end_time - start_time).total_seconds() * 1000
        assert duration_ms < 150  # Should complete in <150ms with parallel processing

    @pytest.mark.asyncio
    async def test_extract_batch_handles_partial_failures(self, extractor, sample_emails):
        """Test that batch processing continues even if some emails fail."""
        # Mock to fail every 3rd email
        original_extract = extractor.extract_from_email
        call_count = [0]

        async def failing_extract(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise Exception("Simulated failure")
            return [
                DiscoveredEntity(
                    tenant_id="tenant-001",
                    workspace_id="workspace-001",
                    _discovered_type="TestEntity",
                    properties={"id": call_count[0]},
                    confidence_score=0.8,
                    source_record_id=f"email-{call_count[0]}",
                    source_record_type="email"
                )
            ]

        extractor.extract_from_email = failing_extract

        # Act
        entities = await extractor.extract_batch(
            sample_emails[:15],  # 15 emails, 5 will fail
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert - Should process non-failing emails
        assert len(entities) == 10  # 15 - 5 failures


# ============================================================================
# Test Class 2: Prompt Caching
# ============================================================================

class TestPromptCaching:
    """Tests for prompt caching system."""

    def test_classify_email_categories(self, extractor):
        """Test email classification into categories."""
        # Purchase order
        po_email = {"subject": "Purchase Order PO-123", "body": "Please approve PO-123"}
        assert extractor._classify_email_category(po_email) == "purchase_order"

        # Security event
        security_email = {"subject": "Security Alert", "body": "Unusual login detected"}
        assert extractor._classify_email_category(security_email) == "security_event"

        # Invoice
        invoice_email = {"subject": "Invoice INV-001", "body": "Payment due"}
        assert extractor._classify_email_category(invoice_email) == "invoice"

        # Ticket
        ticket_email = {"subject": "Support Ticket #123", "body": "Help needed"}
        assert extractor._classify_email_category(ticket_email) == "ticket"

        # Lead
        lead_email = {"subject": "New Lead", "body": "Prospect inquiry"}
        assert extractor._classify_email_category(lead_email) == "lead"

        # General
        general_email = {"subject": "Hello", "body": "Just saying hi"}
        assert extractor._classify_email_category(general_email) == "general"

    @pytest.mark.asyncio
    async def test_prompt_caching_hit_rate(self, extractor, po_emails):
        """Test prompt caching achieves 50%+ hit rate."""
        # Process first batch - all cache misses
        for email in po_emails[:5]:
            extractor._build_extraction_prompt(email)

        # Process second batch - should get cache hits
        for email in po_emails[5:]:
            extractor._build_extraction_prompt(email)

        # Assert
        stats = extractor.cache_stats
        assert stats["total"] == 10
        assert stats["hits"] >= 5  # 50%+ hit rate
        assert stats["misses"] == 5  # First 5 were misses

    def test_cache_hit_rate_calculation(self, extractor):
        """Test cache hit rate calculation."""
        # Initial state
        assert extractor._get_cache_hit_rate() == 0.0

        # Add some stats
        extractor.cache_stats = {"hits": 7, "misses": 3, "total": 10}

        # Assert
        assert extractor._get_cache_hit_rate() == 0.7

    def test_prompt_cache_storage(self, extractor, po_emails):
        """Test that prompts are cached by category."""
        # Build prompt for PO email
        email = po_emails[0]
        prompt1 = extractor._build_extraction_prompt(email)

        # Check cache
        assert "purchase_order" in extractor.prompt_cache
        assert extractor.prompt_cache["purchase_order"] == prompt1

        # Build prompt for another PO email - should hit cache
        email2 = po_emails[1]
        prompt2 = extractor._build_extraction_prompt(email2)

        # Should be same cached prompt
        assert prompt2 == prompt1

    def test_cache_hit_rate_target(self, extractor):
        """Test that cache hit rate reaches 50%+ target."""
        # Simulate processing 20 similar emails
        for i in range(20):
            email = {
                "subject": f"Purchase Order PO-{i}",
                "body": "Please approve"
            }
            extractor._build_extraction_prompt(email)

        # Assert
        hit_rate = extractor._get_cache_hit_rate()
        assert hit_rate >= 0.5  # 50%+ hit rate


# ============================================================================
# Test Class 3: Model Selection
# ============================================================================

class TestModelSelection:
    """Tests for intelligent model selection."""

    def test_simple_email_uses_mini_model(self, extractor, simple_email):
        """Test that simple emails use GPT-4o-mini."""
        # Act
        selected_model = extractor._select_model(simple_email)

        # Assert
        assert selected_model == "gpt-4o-mini"

    def test_complex_email_uses_full_model(self, extractor, complex_email):
        """Test that complex emails use GPT-4o."""
        # Act
        selected_model = extractor._select_model(complex_email)

        # Assert
        assert selected_model == "gpt-4o"

    def test_model_selection_complexity_analysis(self, extractor, simple_email, complex_email):
        """Test complexity analysis for model selection."""
        # Simple email
        simple_complexity = extractor._analyze_email_complexity(simple_email)
        assert simple_complexity["word_count"] < 100
        assert simple_complexity["complexity_score"] < 40

        # Complex email
        complex_complexity = extractor._analyze_email_complexity(complex_email)
        assert complex_complexity["word_count"] > 50
        assert complex_complexity["complexity_score"] >= 40

    def test_model_selection_statistics(self, extractor, simple_email, complex_email):
        """Test model selection statistics tracking."""
        # Reset stats
        extractor.reset_stats()

        # Process mixed emails
        for _ in range(6):
            extractor._select_model(simple_email)  # Uses mini
        for _ in range(4):
            extractor._select_model(complex_email)  # Uses full

        # Assert
        stats = extractor.get_performance_stats()["model_selection"]
        assert stats["gpt_4o_mini_count"] == 6
        assert stats["gpt_4o_count"] == 4
        assert stats["total"] == 10
        assert stats["mini_rate"] == 0.6  # 60%

    def test_mini_model_rate_target(self, extractor):
        """Test that 60%+ of emails use mini model."""
        # Reset stats
        extractor.reset_stats()

        # Process mixed workload (60% simple, 40% complex)
        simple_email = {
            "subject": "Quick",
            "body": "Short message"
        }
        complex_email = {
            "subject": "Complex Legal Review",
            "body": "This is a long legal contract with many technical specifications and financial terms. " * 20
        }

        for _ in range(60):
            extractor._select_model(simple_email)
        for _ in range(40):
            extractor._select_model(complex_email)

        # Assert
        mini_rate = extractor._get_mini_model_rate()
        assert mini_rate == 0.6  # 60% target achieved

    def test_model_selection_disabled(self, extractor, simple_email):
        """Test that model selection can be disabled."""
        # Create extractor with model selection disabled
        extractor_no_selection = MultiEntityLLMExtractor(
            enable_model_selection=False,
            model="gpt-4o"
        )

        # Act
        selected_model = extractor_no_selection._select_model(simple_email)

        # Assert - Should always return default model
        assert selected_model == "gpt-4o"


# ============================================================================
# Test Class 4: Performance Benchmarks
# ============================================================================

class TestPerformanceBenchmarks:
    """Tests for performance benchmarking."""

    @pytest.mark.asyncio
    async def test_batch_processing_speed(self, extractor, sample_emails):
        """Test batch processing speed target (2.4s per email)."""
        import time

        # Act
        start_time = time.time()
        entities = await extractor.extract_batch(
            sample_emails[:10],  # 10 emails
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )
        end_time = time.time()

        # Assert - Should complete in <24 seconds (2.4s per email)
        duration = end_time - start_time
        assert duration < 24.0, f"Batch processing too slow: {duration:.2f}s for 10 emails"

    def test_performance_stats_aggregation(self, extractor):
        """Test performance statistics aggregation."""
        # Reset stats
        extractor.reset_stats()

        # Simulate activity
        extractor.cache_stats = {"hits": 80, "misses": 20, "total": 100}
        extractor.model_stats = {"gpt-4o": 40, "gpt-4o-mini": 60, "total": 100}

        # Act
        stats = extractor.get_performance_stats()

        # Assert
        assert stats["prompt_cache"]["hit_rate"] == 0.8
        assert stats["model_selection"]["mini_rate"] == 0.6

    def test_reset_stats_clears_all_data(self, extractor):
        """Test that reset_stats clears all statistics."""
        # Set some stats
        extractor.cache_stats = {"hits": 50, "misses": 50, "total": 100}
        extractor.model_stats = {"gpt-4o": 30, "gpt-4o-mini": 70, "total": 100}

        # Act
        extractor.reset_stats()

        # Assert
        assert extractor.cache_stats == {"hits": 0, "misses": 0, "total": 0}
        assert extractor.model_stats == {"gpt-4o": 0, "gpt-4o-mini": 0, "total": 0}


# ============================================================================
# Test Class 5: Integration Tests
# ============================================================================

class TestPerformanceIntegration:
    """Integration tests for performance optimizations."""

    @pytest.mark.asyncio
    async def test_end_to_end_batch_with_caching_and_model_selection(self, extractor):
        """Test complete workflow with all optimizations enabled."""
        # Create mixed email batch
        emails = [
            {
                "id": "email-001",
                "subject": "Purchase Order PO-001",
                "from": "vendor1@acme.com",
                "to": ["admin@company.com"],
                "body": "Please approve PO-001 for $1,000."
            },
            {
                "id": "email-002",
                "subject": "Purchase Order PO-002",
                "from": "vendor2@acme.com",
                "to": ["admin@company.com"],
                "body": "Please approve PO-002 for $2,000."
            },
            {
                "id": "email-003",
                "subject": "Simple Question",
                "from": "user@example.com",
                "to": ["support@example.com"],
                "body": "Quick question about account."
            }
        ]

        # Act
        entities = await extractor.extract_batch(
            emails,
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) >= 3  # At least 1 entity per email

        # Check performance stats
        stats = extractor.get_performance_stats()
        assert stats["prompt_cache"]["hit_rate"] > 0  # Some cache hits
        assert stats["model_selection"]["mini_rate"] > 0  # Some mini model usage

    @pytest.mark.asyncio
    async def test_cost_reduction_verification(self, extractor, sample_emails):
        """Verify 30% cost reduction target is achievable."""
        # Process batch
        entities = await extractor.extract_batch(
            sample_emails[:20],
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Calculate cost estimate
        stats = extractor.get_performance_stats()
        mini_rate = stats["model_selection"]["mini_rate"]
        cache_hit_rate = stats["prompt_cache"]["hit_rate"]

        # Cost calculation:
        # - Without optimizations: 20 emails * $0.01 = $0.20
        # - With 60% mini model: 20 * 0.6 * $0.0015 + 20 * 0.4 * $0.01 = $0.098
        # - With 50% cache hits: Additional 25% savings = $0.073
        # - Total savings: 63.5%

        # Assert - Should achieve 30%+ cost reduction
        estimated_cost_without_opt = 20 * 0.01  # $0.20
        mini_model_count = int(20 * mini_rate)
        full_model_count = 20 - mini_model_count
        estimated_cost_with_opt = (
            mini_model_count * 0.0015 +  # Mini model cost
            full_model_count * 0.01      # Full model cost
        ) * (1 - cache_hit_rate * 0.5)   # Cache savings

        cost_reduction = (estimated_cost_without_opt - estimated_cost_with_opt) / estimated_cost_without_opt
        assert cost_reduction >= 0.3, f"Cost reduction only {cost_reduction:.1%}, target 30%+"
