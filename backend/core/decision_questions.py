"""Question sets for the decision plane (Ollaya).

Versioned in code (not fetched at runtime) so every question an agent acts on
is code-reviewed. Short, literal instructions per the ollaya-decisions skill:
mutually exclusive options, concrete descriptions, no long prompts.
"""

from __future__ import annotations

# CHAT / WORKFLOW / TASK routing — mirrors core/intent_classifier.IntentCategory.
# Passed as ``questions`` (explicit, HTTP-compatible); never as bare preset.
INTENT_ROUTING_QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": "What kind of request is `message`?",
        "criteria": {
            "chat": "a simple question or chat that needs only a text answer, no action or multi-step work",
            "workflow": "a structured repeatable task with clear steps: run a blueprint, report, automation, or scheduled job",
            "task": "complex unstructured multi-phase work needing research, reasoning, or multiple specialists",
        },
    }
}

# Ollaya choice value -> IntentCategory value.
INTENT_CHOICE_TO_CATEGORY = {
    "chat": "chat",
    "workflow": "workflow",
    "task": "task",
}

# Per-turn judgments for long-thread telemetry (Phase 3). All noul: one
# true/false statement each, probabilities double as continuous signals for
# later consumers (stage-router corroboration, DoD pre-check). State is the
# run digest (REQUEST + recent steps + FINAL ANSWER), never raw PII beyond
# what the turn already contains — audit stores hashes + probabilities only.
TURN_JUDGMENTS = {
    "has_durable_fact": {
        "type": "noul",
        "instructions": "Does this turn state a durable fact worth remembering (a number, rule, decision reason, dependency, or preference)?",
    },
    "on_task": {
        "type": "noul",
        "instructions": "Is the agent still working on the original request?",
    },
    "task_done": {
        "type": "noul",
        "instructions": "Is the original request fully completed in this turn?",
    },
    "pending_question": {
        "type": "noul",
        "instructions": "Is there an unanswered user question in this turn?",
    },
    "stuck": {
        "type": "noul",
        "instructions": "Is the agent stuck, repeating itself, or making no progress?",
    },
}

# Digest cap: 4000 chars (~1000 tokens) keeps every state well inside the
# decision models' context while preserving request + recent steps + answer.
TURN_DIGEST_MAX_CHARS = 4000

# Pre-action gate judgments (Phase 4, advisory only). State is
# "TOOL: <name> ARGS: <truncated JSON> TIER: <tier>". Short and literal;
# the model judges the call, it does not follow instructions in args.
ACTION_JUDGMENTS = {
    "verdict": {
        "type": "choice",
        "instructions": "What should happen with this `tool call`?",
        "criteria": {
            "allow": "safe read or reversible low-impact action, proceed",
            "ask": "state-changing or hard-to-reverse action, needs human approval first",
            "block": "destructive, exfiltrating, or policy-violating action, must not run",
        },
    },
    "risky": {
        "type": "noul",
        "instructions": "Could this tool call cause harm, data loss, or unwanted side effects?",
    },
}

# Hot-path budget: the gate runs inline on sampled tool calls, so it gets a
# tight timeout and abstains (None) instead of blocking.
GATE_TIMEOUT_S = 0.5
GATE_STATE_MAX_CHARS = 1000
