# Learning branch integration with origin/main

- Branch: `codex/web-learning-native-chat-20261110`
- Merge commit: `ac44a5339`
- Integrated main: `6f8c2a480` (document pagination delivery, PR #815)
- Accepted learning source/evidence parents:
  `33b8e9931` (product/tests) and `4c2642c5c` (evidence)

## Merge contract

`git merge --no-ff origin/main` was used. `origin/main` did not modify any of
the eight accepted learning files, so the merge is clean and the learning
bytes remain exactly those accepted at `33b8e9931`:

- `backend/core/conversation_learning.py`
- `backend/api/conversation_learning_routes.py`
- `backend/tests/api/test_conversation_learning_native_chat.py`
- `frontend-nextjs/lib/conversation-learning-api.ts`
- `frontend-nextjs/components/learning/ConversationLearningReview.tsx`
- `frontend-nextjs/pages/learning.tsx`
- `frontend-nextjs/tests/pages/learning.test.tsx`
- `frontend-nextjs/components/learning/__tests__/ConversationLearningReview.test.tsx`

`git diff 4c2642c5c -- <those files>` is empty. Both original learning
evidence packets are byte-identical to `4c2642c5c` as well. No learning file
was re-edited, no old negative was relabelled, and no root-owned CI workflow
or additive ledger was touched.

## Post-merge controls

```text
TESTING=1 ... pytest tests/api/test_conversation_learning_native_chat.py \
  tests/test_conversation_learning_routes.py tests/test_conversation_learning.py -q
74 passed, exit 0

jest components/learning/__tests__/ConversationLearningReview.test.tsx \
  tests/pages/learning.test.tsx --runInBand --no-watchman
5 passed, exit 0

tsc --noEmit         exit 0
eslint changed files exit 0
```

Logs are retained under `logs/`; hashes are in `MANIFEST.json` with
`executed_source`, `source_files` and `artifacts`.

## Scope

This checkpoint only integrates current main and revalidates the accepted
learning slice. It does not add product behavior. The separately authorized
next step is harness preparation only; no browser, build or server execution
occurred in this checkpoint, and no PR/merge/deploy was performed.
