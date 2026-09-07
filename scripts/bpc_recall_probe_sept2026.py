"""One-off recall probe (Sept 2026 BPC recalibration) — mirrors the Aug 30
methodology from commit 8bd9920de: give the model a transcript where IT
previously stated specific facts, then ask for those facts back. Models that
ignore their own prior assistant turn fail recall and must score below the
SIMPLE conversational floor (85) regardless of general aptitude.

Read-only w.r.t. the app: no DB access, no state writes. Costs < $0.01.
"""

import json
import base64
import sys
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
    "minimax/minimax-m3",             # control — passed Aug 30
    "qwen/qwen3.7-flash",             # control — failed Aug 30
    "google/gemini-3-flash-preview",
    "openai/gpt-5-mini",
    "z-ai/glm-5.3-flash",
    "qwen/qwen3.8-flash",
    "deepseek/deepseek-v4-flash-0731",
]

results = {}
with httpx.Client(timeout=60) as client:
    for model in MODELS:
        results[model] = {}
        for name, msgs in (("recall", TRANSCRIPT), ("followup", FOLLOWUP)):
            try:
                r = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": msgs, "max_tokens": 200, "temperature": 0},
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"] or ""
                usage = r.json().get("usage", {})
            except Exception as e:
                text = f"<error: {type(e).__name__}: {e}>"
                usage = {}
            hit = ("INV-20948" in text, "Mark Kellam" in text or "WFS" in text)
            passed = ("error" not in text) and name == "recall" and all([text is not None]) and hit[0] and hit[1] if name == "recall" else ("error" not in text and "INV-20948" in text)
            results[model][name] = {"pass": bool(passed), "facts": hit, "usage": usage, "reply": text[:300]}
            print(f"{model:38s} {name:9s} pass={passed} facts={hit}")

print()
for m, r in results.items():
    print(m, "->", "RECALL-PASS" if (r["recall"]["pass"] and r["followup"]["pass"]) else "RECALL-FAIL")
json.dump(results, open(Path(__file__).parent / "recall_probe_results.json", "w"), indent=1)
