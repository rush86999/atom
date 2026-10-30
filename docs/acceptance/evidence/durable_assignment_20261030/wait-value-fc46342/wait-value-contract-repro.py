"""Direct reproduction of the verifier's alternate-representation bypasses."""
import json
import sys

from core.assignment_executor import _source_fact_resolution


def record(result, *, coverage=None, columns=None):
    return {"assignment": {"steps": [{
        "step_id": "source", "status": "applied",
        "inputs": {"resource_binding": {
            "columns": columns or ["Currency", "__sheet_row"],
            "coverage": coverage or {
                "known": True, "source_row_count": 2, "truncated": False},
        }},
        "result": result,
    }]}}


def inline(rows, accepted, *, coverage_truncated=False,
           result_truncated=False):
    result = {
        "rows": rows,
        "selected_count": len(accepted),
        "truncated": result_truncated,
        "evidence": [{
            "sheet_rows": accepted,
            "selected_count": len(accepted),
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": coverage_truncated},
        }],
    }
    return record(result, coverage={
        "known": True, "source_row_count": 2,
        "truncated": coverage_truncated})


cases = {
    "inline_complete": (
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2]), "currency"),
    "inline_coverage_truncated": (
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2],
               coverage_truncated=True), "currency"),
    "inline_result_truncated": (
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2],
               result_truncated=True), "currency"),
    "inline_missing_accepted_row": (
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2, 3]), "currency"),
    "inline_absent_field": (
        inline([{"__sheet_row": 2}], [2]), "currency"),
    "aggregate_subtotal_wrong_fact": (
        record({"measure": "Price",
                "subtotals": {"USD": {"value": "35.00"}}},
               coverage={"known": True, "source_row_count": 1,
                         "truncated": False},
               columns=["Price", "Currency", "__sheet_row"]), "price"),
    "aggregate_values_unbound_dimension": (
        record({"measure": "Price",
                "values": [{"currency": "USD", "value": "400.00"}]},
               coverage={"known": True, "source_row_count": 1,
                         "truncated": False}), "currency"),
    "aggregate_bound_dimension": (
        record({"measure": "Price", "group_by": "currency",
                "values": [{"currency": "USD", "value": "400.00"}]},
               coverage={"known": True, "source_row_count": 1,
                         "truncated": False}), "currency"),
}

out = {}
for name, (rec, fact) in cases.items():
    resolution = _source_fact_resolution(rec, fact)
    out[name] = {
        "status": resolution.get("status"),
        "reason": resolution.get("reason"),
        "values": resolution.get("values"),
    }
print(json.dumps(out, indent=2, sort_keys=True))
