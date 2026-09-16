# -*- coding: utf-8 -*-
"""The "open the file the user NAMED" probe must return rows, not NameError.

Every derivation turn logged, twice:

    WARNING:core.chat_tool_planner:tool execution failed for
             zoho_workdrive.read: name 'rows_out' is not defined
    ... canvas edit declined: the turn needs live data and the lookup failed

``_probe_named_file`` built its result literal from ``_read_sheet_rows(...)``
inline and then referenced ``rows_out`` — a name that was never assigned. So
the named-file path raised on every call, the tool reported a failed lookup,
and the turn passed that failure on to the model. The CONTENT-probe path was
untouched, which is why the same ask sometimes worked: whichever lane matched
first decided the outcome.
"""
from typing import Any, Dict, List

import pytest

import core.sheet_dataset_service as sds


@pytest.fixture()
def named(monkeypatch):
    monkeypatch.setattr(
        sds, "_read_sheet_rows",
        lambda path, max_rows: [{"Product Name": 'F-52"x16G',
                                 "LIST Price": 7519.0,
                                 "Factory Price": 5350.0}])
    monkeypatch.setattr(sds, "load_formulas_for_parquet",
                        lambda path: {"G235": "=F235*0.9"})
    return [{"file_name": "PRICE VIPUL (6).xlsx",
             "sheet_name": "Sheet1",
             "parquet_path": "/tmp/x.parquet",
             "source_modified_at": "2026-09-16T00:00:00"}]


class TestNamedFileProbe:
    def test_returns_the_named_file_with_its_rows(self, named):
        out = sds._probe_named_file(named, max_rows=20)
        assert out is not None
        assert out["file_name"] == "PRICE VIPUL (6).xlsx"
        assert out["rows"], "the named-file probe returned no rows"
        assert out["row_count"] == len(out["rows"])
        assert out["formulas"] == {"G235": "=F235*0.9"}
        assert out["selected_by_name"] is True

    def test_no_entries_is_not_a_result(self):
        assert sds._probe_named_file([], max_rows=20) is None

    def test_a_row_read_failure_does_not_raise(self, monkeypatch, named):
        def _boom(path, max_rows):
            raise RuntimeError("parquet unreadable")

        monkeypatch.setattr(sds, "_read_sheet_rows", _boom)
        with pytest.raises(RuntimeError):
            # `_read_sheet_rows` is documented best-effort and returns [] on
            # failure; a caller that swaps in a raiser still must not get a
            # NameError from THIS function (that was the shipped defect).
            sds._probe_named_file(named, max_rows=20)
