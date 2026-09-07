"""Recall probe v2 (Sept 2026 BPC recalibration) — structural fixes over v1:

v1 artifact: max_tokens=200 starved REASONING flash models — glm-5.3-flash /
deepseek-v4-flash-0731 / qwen3.7-flash burned the whole budget on
reasoning_tokens and returned EMPTY content (finish_reason=length), which v1
misclassified as recall failure. The user called this correctly: a trivial
transcript-recall task should not fail unless something is structural.

v2 rules:
- max_tokens=2000 (production chat uses ATOM_COMPLETION_MAX_TOKENS=6000)
- finish_reason recorded; "length"-capped with empty content => INCONCLUSIVE
- 429 => retry with backoff (v1 misclassified a rate-limit as a miss)
- 2s spacing between calls
- "no-access" language detected separately (the Aug-30 failure signature)

Read-only w.r.t. the app: no DB access, no state writes. Costs < $0.05.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from cryptography.fernet import Fernet  # noqa: E402
import httpx  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "backend" / "data"
keys = json.load(open(ROOT / "byok_keys.json"))
entry = next(
    v for v in keys["keys"].values()
    if v.get("provider_id") == "openrouter" and v.get("is_active") and v.get("last_used")
)
f = Fernet(open(ROOT / "byok_encryption_key", "rb").read().strip())
api_key = f.decrypt(entry["encrypted_key"].encode()).decode()

TRANSCRIPT = [
    {"role": "system", "content": "You are Atom, a helpful business assistant."},
    {"role": "user", "content": "Hi, I'm Sarah from Blumetric. My account manager is Mark Kellam at WFS Ltd, and my invoice number is INV-20948."},
    {"role": "assistant", "content": "Thanks Sarah! I've noted that down: your account manager is Mark Kellam at WFS Ltd, and your invoice number is INV-20948. What can I help you with today?"},
    {"role": "user", "content": "Quick question before we continue: what invoice number did I give you earlier, and who is my account manager?"},
]
FOLLOWUP = [
    {"role": "system", "content": "You are Atom, a helpful business assistant."},
    {"role": "user", "content": "My account manager is Mark Kellam at WFS Ltd, and my invoice number is INV-20948. Please draft a one-line payment reminder for the invoice."},
    {"role": "assistant", "content": "Certainly: 'Hi Sarah, friendly reminder that invoice INV-20948 (WFS Ltd, account manager Mark Kellam) is due. Please arrange payment at your earliest convenience.'"},
    {"role": "user", "content": "Sorry, which invoice number was that reminder about again?"},
]

MODELS = [
    "minimax/minimax-m3",                # control — passed Aug 30 + v1
    "qwen/qwen3.7-flash",                # "failed" Aug 30 — v2 re-test
    "google/gemini-3-flash-preview",
    "openai/gpt-5-mini",
    "z-ai/glm-5.3-flash",                # v1 INCONCLUSIVE (length-capped)
    "qwen/qwen3.8-flash",                # v1 followup was a 429
    "deepseek/deepseek-v4-flash",        # Aug-30 demote to 84 — re-validate
    "deepseek/deepseek-v4-flash-0731",   # v1 INCONCLUSIVE (length-capped)
]

NO_ACCESS = ("don't have access", "do not have access", "no access",
             "don't have any information", "unable to access",
             "don't have access to previous", "cannot see", "can't see")


def call(client, model, msgs):
    for attempt in range(4):
        try:
            r = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": msgs,
                      "max_tokens": 2000, "temperature": 0},
            )
            if r.status_code == 429:
                wait = 6 * (attempt + 1)
                print(f"    429 for {model}, retrying in {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            j = r.json()
            msg = j["choices"][0]["message"] or {}
            return {
                "content": msg.get("content") or "",
                "reasoning": (msg.get("reasoning_content") or "")[:200],
                "finish": j["choices"][0].get("finish_reason"),
                "usage": j.get("usage", {}),
            }
        except Exception as e:
            if attempt == 3:
                return {"error": f"{type(e).__name__}: {e}", "finish": None,
                        "content": "", "reasoning": "", "usage": {}}
            time.sleep(4)
    return {"error": "exhausted retries", "finish": None, "content": "",
            "reasoning": "", "usage": {}}


results = {}
with httpx.Client(timeout=120) as client:
    for model in MODELS:
        results[model] = {}
        for name, msgs in (("recall", TRANSCRIPT), ("followup", FOLLOWUP)):
            out = call(client, model, msgs)
            text = out.get("content", "")
            facts = ("INV-20948" in text, ("Mark Kellam" in text or "WFS" in text))
            capped_empty = out.get("finish") == "length" and not text.strip()
            no_access = any(p in text.lower() for p in NO_ACCESS)
            if capped_empty:
                verdict = "INCONCLUSIVE(length-capped)"
            elif out.get("error"):
                verdict = f"ERROR({out['error'][:60]})"
            elif all(facts) and not no_access:
                verdict = "PASS"
            else:
                verdict = "FAIL" + (" [no-access language]" if no_access else "")
            results[model][name] = {"verdict": verdict, "facts": facts,
                                    "no_access": no_access, **out}
            print(f"{model:36s} {name:9s} {verdict}  facts={facts} finish={out.get('finish')}")
            time.sleep(2)
        print()

print("SUMMARY")
for m, r in results.items():
    print(f"  {m:36s} recall={r['recall']['verdict']:28s} followup={r['followup']['verdict']}")
json.dump(results, open(Path(__file__).parent / "recall_probe_v2_results.json", "w"), indent=1)
