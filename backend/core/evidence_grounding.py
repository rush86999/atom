"""Evidence-grounding contract shared by every LLM path that can produce a
factual claim (chat replies, canvas co-editor edits, drafts).

Live incident (2026-09-02, Mark Kellam canvas): internal guidance said "the
right response is to ask about the job application and CONFIRM 480V 3-phase
specs" — an instruction to verify. The drafting turn asserted the claim as
fact ("the machines are available in 480V 3-phase configuration"). Nothing in
the ingested documents supported it; the "evidence" was a sentence in an
earlier conversation, which itself was just the instruction. Weak models
treat conversation as evidence — this contract is injected into the system
prompts so a claim has to be grounded in THIS context's actual evidence
blocks (tool results, ingested documents, the user's own words), and when it
can't be, the model takes the negative path (say it's unverified) or the
middle path (confirmation-in-progress wording that claims nothing).
"""
import re

EVIDENCE_GROUNDING_RULE = """EVIDENCE GROUNDING — conversation is not evidence:
- State a fact as true ONLY when it is supported by evidence present in THIS
  context: live tool results, ingested documents or memory blocks, or the
  user's own statements. What an earlier conversation (even this transcript)
  asserted is NOT evidence — it may itself have been unverified.
- If you cannot ground a factual claim in the evidence present, choose ONE:
  * Negative path — say so plainly: "I can't confirm X from the data
    available."
  * Middle path — make no claim in either direction. Either word it as
    confirmation-in-progress ("We are confirming X and will follow up
    with details"), or ask for the missing information ("Could you share
    the machine spec sheets so we can confirm the voltage options?") —
    a question asserts nothing.
- Never upgrade an instruction to verify or confirm something ("confirm X",
  "check X") into an assertion that X is true."""

# Artifact-facing tightening: canvas content gets SENT to third parties, so
# an unverified claim in it is the worst-case outcome of a grounding miss.
CANVAS_ARTIFACT_GROUNDING_RULE = """EVIDENCE GROUNDING FOR THE ARTIFACT — this canvas may be sent
to third parties. When the request asks you to add or keep a factual claim
you cannot ground in the current canvas content or the evidence blocks in
this prompt:
- Leave the claim out, or render it as confirmation-in-progress ("We are
  confirming X and will follow up with details") — wording that asserts
  nothing. Asking the reader FOR the missing detail works too ("Could you
  share the machine spec sheets so we can confirm the voltage options?") —
  a question makes no claim in either direction.
- Say plainly in `reply` that the claim is unverified rather than silently
  writing it into the artifact.
Never upgrade an instruction to verify/confirm something into an assertion
that it is true."""


# Deterministic backstop for the live incident's shape: the instruction asks
# to CONFIRM/VERIFY something, but the produced text asserts it as an
# established fact. False positives are acceptable (it only triggers a
# caution); false negatives leave the hallucination in the artifact.
_ASSERTION_MARKERS = re.compile(
    r"\b(?:is|are|was|were|has\s+been|have\s+been)\s+(?:available|confirmed|"
    r"supported|verified|compatible|offered)\b",
    re.IGNORECASE,
)
_CONFIRM_INSTRUCTION = re.compile(
    r"\b(?:confirm\w*|verif\w*|validat\w*|check\w*)\b", re.IGNORECASE
)

# A sentence ends at ., !, ? or a newline. Question sentences assert
# nothing ("Could you confirm whether the unit is available in 480V?") —
# they ARE the middle path, so they never trip the detector even when they
# contain an assertion-marker phrase.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\n])\s+")
_INTERROGATIVE = re.compile(r"^\s*(?:who|what|when|where|which|why|how|"
                            r"could|can|would|will|do|does|did|is|are|"
                            r"please share|kindly share)\b.*\?\s*$", re.IGNORECASE)


def asserts_unverified_confirmation(instruction: str, produced_text: str) -> bool:
    """True when ``instruction`` only asks to confirm/verify a thing and
    ``produced_text`` asserts that thing as already available/confirmed.

    Heuristic gate (unit-tested): fires on the observed hallucination shape —
    "confirm 480V 3-phase availability" → "the machines ARE AVAILABLE in
    480V 3-phase configuration" — so callers can regenerate with the
    grounding contract before the claim reaches the user or the artifact.
    Interrogative sentences are exempt: asking for the missing information
    makes no claim in either direction."""
    if not instruction or not produced_text:
        return False
    if not _CONFIRM_INSTRUCTION.search(instruction):
        return False
    for sentence in _SENTENCE_SPLIT.split(produced_text):
        if not _ASSERTION_MARKERS.search(sentence):
            continue
        if sentence.strip().endswith("?") or _INTERROGATIVE.match(sentence.strip()):
            continue
        return True
    return False
