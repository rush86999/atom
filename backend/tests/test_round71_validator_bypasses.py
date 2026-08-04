"""RED tests — Round 71: bypasses in the B-series security validators.

These tests assert the *secure* behavior and are expected to FAIL against the
current code (they document confirmed bugs found by edge-case probing of the
B1–B10 fixes). They go green once the validators are hardened.

Findings under test:
  B11 — `_validate_data_code` dunder guard is bypassable via
        `getattr(obj, '__cl' + 'ass__')` (concatenation defeats the literal
        Attribute-node scan; the tripwire's getattr check only fires when the
        first arg is a literal module name). Since analyze_data runs the code
        in a full-Python sandbox, this is a complete pyjail escape → RCE.
        (`tools/data_analysis_tool.py:50-52`)
  B13 — `_validate_identifier` raises an unhandled TypeError on non-string
        input; `run_model(feature_columns=[1])` crashes with 500 instead of
        returning a clean validation error.
        (`tools/data_analysis_tool.py:_validate_identifier` +
         `tools/predictive_tools.py:run_model`)

NOTE on B12 (withdrawn): an initial probe suggested splitting a restricted
function name across whitespace (`read\ncsv_auto`) would bypass the SQL
substring scan. Verified against the DuckDB grammar (Keywords & Identifiers
docs): whitespace inside a function name is NOT valid syntax unless the name
is double-quoted as an identifier — and the double-quoted form still contains
the literal token, which the scan catches. So the whitespace "bypass" is a
parser error, not an exploitable read. Test removed to avoid misleading
future readers.

TDD: red first, then fix.
"""
import pytest


# --- B11: getattr + concatenated dunder bypasses the pyjail guard -----------


@pytest.mark.parametrize(
    "payload",
    [
        # Concatenated dunder name defeats the ast.Attribute literal scan.
        "x = getattr(df, '__cl' + 'ass__')",
        # getattr on a non-module object isn't in the tripwire's module list.
        "x = getattr(df, '__class__')",
        # __getattribute__ with a concatenated dunder.
        "x = df.__getattribute__('__ba' + 'se__')",
    ],
)
def test_validate_data_code_blocks_getattr_dunder_concat(payload):
    """B11: any path to a dunder attribute must be blocked, including
    getattr()/__getattribute__ with string-concatenated names. The current
    dunder scan only inspects literal ast.Attribute nodes, so this escapes."""
    from tools.data_analysis_tool import _validate_data_code

    violation = _validate_data_code(payload)
    assert violation is not None, (
        f"B11 regression: dunder access via reflection was allowed.\n"
        f"payload={payload!r}\nviolation={violation!r}"
    )


# --- B13: non-string identifier crashes run_model ---------------------------


@pytest.mark.asyncio
async def test_run_model_non_string_feature_columns_returns_clean_error():
    """B13: run_model must validate feature_columns element types and return a
    clean error dict, not raise TypeError (which surfaces as a 500). Currently
    _validate_identifier passes the raw value to re.fullmatch which TypeErrors
    on non-string input — this happens during validation, before any dataset
    is touched."""
    from tools.predictive_tools import run_model

    result = await run_model(
        dataset_name="ds",
        target_column="y",
        feature_columns=[1, 2, 3],  # non-string elements
        model_type="regression",
        session_id="b13",
    )
    assert isinstance(result, dict), (
        "B13 regression: run_model raised instead of returning an error dict"
    )
    assert result.get("success") is False, (
        f"B13 regression: expected clean validation error, got {result}"
    )
