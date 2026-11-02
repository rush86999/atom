# Probe note — stale-answer refusal expectation

The repaired service refuses a stale answer with `CapabilityError` (the public
route returns 409, matching every other canvas-service refusal).

- `/private/tmp/test_verifier_canvas_boundaries.py` (third case) wraps the
  direct call in `pytest.raises(CapabilityError)` and passes, including the
  assertion that the replacement dataset `B` remains.
- `/private/tmp/test_verifier_canvas_lost_update.py` calls the same direct
  service without `pytest.raises`; it now errors at the expected refusal
  before reaching its durability assertion. It does not represent a source
  overwrite — the exception is raised after validation and before any edit.
- Equivalent controls with the expectation made explicit are in
  `backend/tests/test_canvas_typed_fields.py`:
  `test_stale_session_old_answer_cannot_replace_newer_source` and
  `test_writer_after_validation_but_before_cas_wins`. Both assert source `B`,
  its revision and the absence of a resolved old question in a new session.

No verifier probe file was modified.
