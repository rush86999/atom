# Learning & Verification — End-User Guide

**Where:** Admin sidebar → *Learning & Verification* (or Settings → Advanced → Learning & Verification). Admin role required.

This guide explains the two systems on that page: how your agents **learn from
your ratings**, and how AI judges **verify the answers that matter most**.

---

## 1. Learning from your ratings

Every time you rate a chat answer (thumbs up / thumbs down), Atom saves the
whole exchange — your question and the full answer — as a permanent *example*.
Over time each workspace builds a library made of two halves, and **both
halves matter**:

| You give | It becomes | What the agent does with it |
|---|---|---|
| 👍 Thumbs up | An **approved example** — the shape of a good answer | On similar future questions, similar approved answers can be shown to the agent as demonstrations to imitate |
| 👎 Thumbs down | A **rejected pattern** — where the line is | Similar future questions surface a caution: requests like this were rejected, here is why |
| 👎 + a written comment | A **correction lesson** — permanent, standing guidance | Taught to every student agent in the workspace; applied on *every* future turn, survives graduation |

### Comments are corrections

A thumbs-down tells the agent *that* something was wrong; a comment tells it
*what*. That's why **a rejection with a comment becomes a permanent lesson**
("a human rejected this because … don't repeat that approach"), while a bare
thumbs-down is kept as a caution only — a vague lesson would teach nothing.
Write the comment; that's the highest-leverage feedback you can give.

### Recurring problems get distilled

When several similar rejections with comments pile up on the same topic, the
hourly maintenance cycle merges them into **one pattern-level lesson** instead
of letting duplicates stack. Each pattern is distilled once.

### What the agent never sees

- Failed/error turns are never stored as examples (an infrastructure failure
  is not a content lesson).
- Nothing is inferred: only your explicit ratings (and pressing regenerate,
  which counts as thumbs-down) create examples.
- The same rejection is stored once, even if you rate it twice.

### Modes

| Mode | Learning from ratings | Answers shaped by examples |
|---|---|---|
| `off` | ✗ | ✗ |
| `shadow` *(default, recommended)* | ✓ — lessons, cautions, mastery | ✗ — replies are unchanged |
| `enforce` | ✓ | ✓ — similar approved answers and rejected patterns are surfaced to the agent while it answers |

Learning itself (storage, lessons, mastery growth) happens in shadow and
enforce alike. The flag only controls whether answers are shaped.

---

## 2. Verification panel (AI judges)

On **mission-critical or complex turns**, three AI judges independently check
the answer against the evidence it was written from (tool results, retrieved
documents) and **vote**.

| Mode | Verdicts | Answers |
|---|---|---|
| `off` *(default)* | ✗ | unchanged |
| `shadow` | ✓ recorded | unchanged |
| `enforce` | ✓ recorded | An answer a judge **majority** finds ungrounded is regenerated **once**; if it still fails, an honest caveat is attached instead of pretending |

Judges only run where the stakes justify the cost — ordinary simple chat never
pays for the panel.

---

## 3. Auto-promotion (opt-in)

Both features start conservative (`shadow` for learning, `off` for the panel —
the panel costs extra AI calls per turn, so turning it on at all is a manual
decision). If you arm **auto-promotion** for a feature, the hourly maintenance
cycle will latch it forward by itself — but only when the evidence is healthy,
and only forward:

- **Learning:** promotes `shadow → enforce` once the rated library has
  20+ exchanges with at least 3 approved and 3 rejected (configurable).
- **Panel:** promotes `shadow → enforce` once its run record shows
  ≥ 20 runs, ≥ 90% completed, and meaningful judge agreement (configurable).

Auto-promotion **never demotes**, never turns a paid feature on from `off`,
and **never overrides an environment variable** — if the flag is set in
`.env`, that wins and the page control locks.

---

## 4. Managing it

On the page:

- **Status cards** show the current mode and health: rated counts
  (approved / rejected / total), panel runs, completion rate, mean judge
  agreement.
- **Controls** cover both mode flags, both auto-promotion switches, and the
  health thresholds (corrections-per-lesson, panel gates). Each control shows
  where its value comes from: *default*, *UI setting* (change and reset here),
  or *env override* (locked — remove the env var to manage it here).
- Changes take effect within about a minute (settings cache) — for prompt
  changes, from the next turn.

The underlying flag keys, for `.env` / automation:

| Key | Values | Default |
|---|---|---|
| `ATOM_EXCHANGE_MEMORY` | `off` / `shadow` / `enforce` | `shadow` |
| `ATOM_EXCHANGE_AUTO_PROMOTE` | `true` / `false` | `false` |
| `ATOM_EXCHANGE_DISTILL_MIN` | integer | `3` |
| `ATOM_VERIFY_PANEL` | `off` / `shadow` / `enforce` | `off` |
| `ATOM_VERIFY_PANEL_AUTO_PROMOTE` | `true` / `false` | `false` |
| `ATOM_VERIFY_PANEL_MIN_RUNS` | integer | `20` |
| `ATOM_VERIFY_PANEL_MIN_RAN_RATE` | float 0–1 | `0.9` |
| `ATOM_VERIFY_PANEL_MIN_AGREEMENT` | float 0–1 | `0.5` |

---

## 5. Recommended rollout

1. Rate answers as you normally would — learning is already on in `shadow`.
   Write comments when something's wrong.
2. Give it a week of real usage (the status cards show the corpus growing).
3. Arm auto-promotion if you want `enforce` to switch on by itself once the
   library is big enough — or flip `ATOM_EXCHANGE_MEMORY` to `enforce`
   yourself whenever you like.
4. For the panel, flip it to `shadow` first, watch the completion rate and
   agreement on the status cards for a while, then either arm its
   auto-promotion or set `enforce` manually.
