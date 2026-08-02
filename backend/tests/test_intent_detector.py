"""Tests for the domain/intent detector (Feature 2 of the Manifest gap-analysis work).

Covers: per-category detection, confidence thresholds, null-on-weak-signal,
structural signal boosts, tool-prefix heuristics, session stickiness, tier
nudging, and the cognitive-tier-service integration.
"""
import pytest

from core.llm.intent_detector import (
    INTENT_CATEGORIES,
    IntentDetector,
    IntentResult,
    get_intent_detector,
    is_valid_intent,
)


@pytest.fixture(scope="module")
def detector() -> IntentDetector:
    return IntentDetector()


# --- Category detection -----------------------------------------------------


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("debug this function traceback and fix the api endpoint", "coding"),
        ("refactor the class method and add unit test coverage", "coding"),
        ("the docker kubernetes deployment has a stack trace", "coding"),
        ("analyze this csv dataset with pandas regression correlation", "data_analysis"),
        ("compute the median and visualize the distribution chart", "data_analysis"),
        ("search the web for the latest news and current prices", "web_browsing"),
        ("scrape this website url for real-time data", "web_browsing"),
        ("write a poem about a brave protagonist in a narrative", "creative_writing"),
        ("write a song with lyrics and a chorus verse", "creative_writing"),
        ("prove this theorem step by step using logical deduction", "reasoning"),
        ("derive the formula because therefore it implies", "reasoning"),
    ],
)
def test_detects_expected_category(detector, prompt, expected):
    result = detector.detect(prompt)
    assert result.category == expected, (
        f"expected {expected!r} for {prompt!r}, got {result.category!r}"
    )
    assert 0.0 <= result.confidence <= 1.0


def test_coding_with_code_fence(detector):
    # A code fence alone contributes +2, enough to clear the threshold of 3
    # when combined with any single coding keyword.
    result = detector.detect("here is some code:\n```\nprint('hello')\n```")
    assert result.category == "coding"


def test_url_boosts_web_browsing(detector):
    result = detector.detect("check this out https://example.com")
    assert result.category == "web_browsing"


def test_reasoning_connectives_boost(detector):
    # "therefore" etc. are long-form reasoning connectives (+2).
    result = detector.detect("we must therefore consider the implications")
    assert result.category == "reasoning"


# --- Null on weak / ambiguous signal ----------------------------------------


def test_empty_prompt_returns_none(detector):
    assert detector.detect("").category is None
    assert detector.detect("   ").category is None


def test_single_greeting_below_threshold(detector):
    # "hi" alone is weight 1, below the conversation threshold of 2.
    result = detector.detect("hi")
    assert result.category is None


def test_unrelated_text_returns_none(detector):
    # No keyword matches any category.
    result = detector.detect("the quick brown fox jumps over the lazy dog")
    assert result.category is None


def test_confidence_zero_when_none(detector):
    result = detector.detect("xyzzy floobar bazqux")
    assert result.confidence == 0.0


# --- Strong coding prompt beats weak conversation ---------------------------


def test_coding_dominates_conversation(detector):
    # "hi" (conversation +1) + "debug" (coding +3) -> coding wins.
    result = detector.detect("hi, can you debug this function?")
    assert result.category == "coding"


# --- Tool-prefix heuristics -------------------------------------------------


def test_tool_prefix_browser(detector):
    result = detector.detect("do the thing", tools=[{"name": "browser_navigate"}])
    assert result.category == "web_browsing"


def test_tool_prefix_code(detector):
    result = detector.detect("do the thing", tools=[{"name": "code_execute"}])
    assert result.category == "coding"


def test_tool_prefix_object_attribute(detector):
    class FakeTool:
        name = "github_pr_merge"
    result = detector.detect("do the thing", tools=[FakeTool()])
    assert result.category == "coding"


def test_tool_prefix_string(detector):
    result = detector.detect("do the thing", tools=["sql_query_runner"])
    assert result.category == "data_analysis"


def test_no_tools_no_crash(detector):
    result = detector.detect("analyze the data", tools=None)
    assert result.category == "data_analysis"


def test_empty_tools_list(detector):
    result = detector.detect("analyze the data", tools=[])
    assert result.category == "data_analysis"


# --- Session stickiness -----------------------------------------------------


def test_session_stickiness_adds_bias(detector):
    # "function" alone barely clears coding threshold (weight 3 == threshold 3,
    # confidence 0.33). With 3 matching history turns, the +2 bias raises the
    # score and confidence.
    no_hist = detector.detect("function")
    with_hist = detector.detect("function", recent_intents=["coding", "coding", "coding"])
    assert no_hist.category == "coding"
    assert with_hist.category == "coding"
    assert with_hist.confidence > no_hist.confidence


def test_session_stickiness_needs_min_history(detector):
    # Only 2 matching turns — below STICKY_AGREEMENT_MIN (3), no bias applied.
    short = detector.detect("function", recent_intents=["coding", "coding"])
    assert short.confidence == detector.detect("function").confidence


def test_session_stickiness_disagreement_no_bias(detector):
    # Mixed history — no stickiness.
    mixed = detector.detect("function", recent_intents=["coding", "reasoning", "coding"])
    assert mixed.confidence == detector.detect("function").confidence


# --- Category penalties -----------------------------------------------------


def test_category_penalty_suppresses_winner(detector):
    # coding normally wins for "debug function"; penalize it to None.
    result = detector.detect("debug function", category_penalties={"coding": 10})
    assert result.category is None


# --- Tier nudge -------------------------------------------------------------


@pytest.mark.parametrize(
    "intent,base_tier,expected",
    [
        ("coding", "micro", "versatile"),
        ("coding", "standard", "versatile"),
        ("coding", "versatile", "versatile"),
        ("coding", "heavy", "heavy"),  # no downgrade
        ("reasoning", "standard", "versatile"),
        ("reasoning", "micro", "versatile"),
        ("conversation", "complex", "standard"),
        ("conversation", "heavy", "standard"),
        ("conversation", "standard", "standard"),
        ("conversation", "micro", "micro"),  # no upgrade
        ("data_analysis", "micro", "standard"),
        ("creative_writing", "micro", "standard"),
        ("web_browsing", "heavy", "heavy"),  # no nudge for web_browsing
        ("web_browsing", "micro", "micro"),
        (None, "complex", "complex"),  # None -> no nudge
    ],
)
def test_nudge_tier(detector, intent, base_tier, expected):
    assert detector.nudge_tier(intent, base_tier) == expected


def test_nudge_tier_invalid_base(detector):
    # Invalid tier string returned unchanged (no crash).
    assert detector.nudge_tier("coding", "bogus") == "bogus"


# --- Helpers ----------------------------------------------------------------


def test_is_valid_intent():
    for cat in INTENT_CATEGORIES:
        assert is_valid_intent(cat)
    assert not is_valid_intent("bogus")
    assert not is_valid_intent("")


def test_singleton_returns_same_instance():
    a = get_intent_detector()
    b = get_intent_detector()
    assert a is b


def test_intent_result_dataclass():
    r = IntentResult(category="coding", confidence=0.8)
    assert r.category == "coding"
    assert r.confidence == 0.8
    r_none = IntentResult(category=None, confidence=0.0)
    assert r_none.category is None


# --- CognitiveTierService integration --------------------------------------


def test_select_tier_applies_intent_nudge(monkeypatch):
    """select_tier should nudge the tier when a strong intent is detected."""
    from core.llm.cognitive_tier_service import CognitiveTierService
    from core.llm.cognitive_tier_system import CognitiveTier

    svc = CognitiveTierService(workspace_id="test-ws-intent")
    # "debug this function" is a short, low-complexity prompt that classifies
    # as MICRO or STANDARD by complexity, but the coding intent should floor
    # it at VERSATILE.
    tier = svc.select_tier("debug this function", task_type="code")
    # Whatever the base classification, coding intent floors at VERSATILE.
    order = [
        CognitiveTier.MICRO,
        CognitiveTier.STANDARD,
        CognitiveTier.VERSATILE,
        CognitiveTier.HEAVY,
        CognitiveTier.COMPLEX,
    ]
    assert order.index(tier) >= order.index(CognitiveTier.VERSATILE), (
        f"coding intent should floor tier at VERSATILE, got {tier}"
    )


def test_select_tier_intent_override_skips_detection():
    """An explicit intent_override should be used directly without detection."""
    from core.llm.cognitive_tier_service import CognitiveTierService
    from core.llm.cognitive_tier_system import CognitiveTier

    svc = CognitiveTierService(workspace_id="test-ws-override")
    # A short prompt that would normally classify low, but conversation intent
    # override caps at STANDARD. With override="conversation" applied to a
    # COMPLEX-classified prompt it should come down.
    tier = svc.select_tier(
        "prove this theorem therefore derive the conclusion step by step",
        intent_override="conversation",
    )
    # conversation caps at STANDARD regardless of complexity.
    assert tier == CognitiveTier.STANDARD, f"conversation cap failed, got {tier}"
