# -*- coding: utf-8 -*-
"""Derived figures are checked by EVALUATION, not by citation (audit directive 3).

Two failures this replaces:

1. The orchestrator skipped figure-grounding when the evidence carried a formula
   marker AND the reply contained any row citation — so an INVENTED chain evaded
   verification by writing "row 235" somewhere. A citation does not prove
   arithmetic.
2. The honest half of the old motivation remains true and is preserved: a
   correctly COMPUTED value is absent from the evidence text by construction, so
   a text-presence check cannot call it fabricated. The answer is evaluation.

The contract: STORED (matches a delivered cell), COMPUTED (a delivered formula
reproduces it), UNRESOLVED (dependencies outside the window — unverifiable, and
therefore NOT clean), CONTRADICTED (the formula yields a different number).
"""
import pytest

from core.derivation_verification import (
    CONTRADICTED,
    UNRESOLVED,
    VERIFIED_COMPUTED,
    VERIFIED_STORED,
    parse_evidence,
    verify_derivation_claims,
)

# The live F-5216 row exactly as the evidence block renders it, including the
# COLUMNS bridge that connects column names to the letters the formulas use.
BLOCK = """R235 | Product Name=F-52\u201dx16G | Capacity= | LIST Price=7519.0 | Factory Price=5350 | Factory Discount=4815.0 | Exchange=4815.0 | Freight=5515.0 | CSA=5515.0 | Warehouse=5625.3 | Brennan Margin=6465.862068965517
COLUMNS: Product Name=A | c2=B | Capacity=C | LIST Price=D | Vipul Selling price=E | Factory Price=F | Factory Discount=G | Exchange=H | Freight=I | CSA=J | Warehouse=K | Brennan Margin=L
FORMULAS FOR THE MATCHED ROW(S) \u2014 the derivation the original workbook computes (cell=formula): D235==P235 | G235==F235*0.9 | H235==G235 | I235==H235+700 | J235==I235 | K235==J235*1.02 | L235==K235/0.87 | M235==L235/0.86 | N235==ROUNDUP(M235,0) | P235==N235*O235
R169 | Product Name=Roper Whitney | LIST Price=126192.0 | Factory Price=69250 | Factory Discount=58862.5
FORMULAS FOR THE MATCHED ROW(S) \u2014 context: D169==ROUNDUP(P169,0) | G169==0.85*F169 | H169==G169*U2"""


class TestParseEvidence:
    def test_values_formulas_and_the_column_bridge(self):
        values, formulas, rows = parse_evidence(BLOCK)
        assert formulas["G235"] == "F235*0.9"
        assert values.get("F235") == 5350.0          # via the COLUMNS bridge
        assert "235" in rows and "169" in rows

    def test_malformed_block_is_empty_not_an_error(self):
        for bad in ("", None, "not an evidence block", "R### | broken"):
            values, formulas, rows = parse_evidence(bad or "")
            assert isinstance(values, dict) and isinstance(formulas, dict)


class TestTheFiveRequiredCases:
    def test_correct_chain_verifies(self):
        v = verify_derivation_claims(
            "G235 = 4815, I235 = 5515, K235 = 5625.30, L235 = 6465.86, "
            "M235 = 7518.44, N235 = 7519",
            BLOCK,
        )
        assert v.is_clean, v.summary()
        assert v.checked >= 5
        assert all(
            fv.status in (VERIFIED_STORED, VERIFIED_COMPUTED) for fv in v.verdicts
        )

    def test_invented_intermediate_is_contradicted(self):
        v = verify_derivation_claims("G235 = 4815 and K235 = 7000", BLOCK)
        assert not v.is_clean
        assert [fv.figure for fv in v.contradicted] == [7000.0]
        assert "5625.3" in v.contradicted[0].detail

    def test_wrong_row_is_contradicted(self):
        """Row 169's cells do not hold row 235's values."""
        v = verify_derivation_claims("F169 = 5350, G169 = 4815", BLOCK)
        assert not v.is_clean
        assert len(v.contradicted) == 2

    def test_unrelated_formula_cannot_validate_a_claim(self):
        """A figure attributed to a cell whose formula yields something else."""
        v = verify_derivation_claims("G235 = 8880", BLOCK)
        assert not v.is_clean and v.contradicted

    def test_genuine_stored_value_verifies_without_arithmetic(self):
        """The list price is a STORED value — no formula evaluation needed."""
        v = verify_derivation_claims("The list price on row 235 is 7519", BLOCK)
        assert not v.contradicted
        stored = [fv for fv in v.verdicts if fv.status == VERIFIED_STORED]
        assert stored and stored[0].figure == 7519.0


class TestUnverifiedIsNeverClean:
    def test_citation_alone_proves_nothing(self):
        """The exact hole this replaces: 'row 235' used to satisfy the check."""
        v = verify_derivation_claims("See row 235 for the derivation.", BLOCK)
        assert not v.is_clean
        assert v.claims == 0
        assert "no cell-anchored claim" in v.summary()

    def test_a_correct_uncited_answer_is_unverified_not_failed(self):
        """Directive 4's both-directions case: prose can omit the citation.

        A correct calculation that never names a cell must NOT be reported as a
        fabrication — but it is also not verified. Unverified is the honest
        verdict, and it is not clean.
        """
        v = verify_derivation_claims(
            "The factory price of 5350 less 10% is 4815; adding 700 gives 5515.",
            BLOCK,
        )
        assert not v.contradicted, "a correct uncited answer must not be called wrong"
        assert not v.is_clean, "it was not checked, so it is not grounded either"

    def test_missing_dependency_is_unresolved(self):
        v = verify_derivation_claims("Z235 = 12345", BLOCK)
        assert not v.is_clean
        assert any(fv.status == UNRESOLVED for fv in v.verdicts)
        assert "Z235" in v.unresolved_cells

    def test_no_evidence_means_nothing_claimed(self):
        v = verify_derivation_claims("G235 = 4815", "")
        assert v.claims == 0 and not v.is_clean


class TestEvaluationIsBounded:
    """A formula evaluator on untrusted text must not execute arbitrary code."""

    def test_unknown_functions_are_unresolved_not_executed(self):
        v = verify_derivation_claims("G235 = 1", "R235 | x=1\nFORMULAS FOR THE MATCHED ROW(S): G235==__import__('os').system('echo hi')")
        assert not v.is_clean
        assert not v.contradicted or all("os" not in fv.detail for fv in v.contradicted)

    def test_circular_references_do_not_hang(self):
        v = verify_derivation_claims(
            "G235 = 5", "R235 | x=1\nFORMULAS FOR THE MATCHED ROW(S): G235==H235 | H235==G235"
        )
        assert not v.is_clean  # unresolved, and it returned at all

    def test_division_by_zero_is_unresolved(self):
        v = verify_derivation_claims(
            "G235 = 5", "R235 | x=1\nFORMULAS FOR THE MATCHED ROW(S): G235==F235/0 | F235==0"
        )
        assert not v.is_clean

    @pytest.mark.parametrize("fn,expected", [("ROUNDUP(M235,0)", 7519.0), ("ROUND(M235,0)", 7518.0)])
    def test_supported_functions_evaluate(self, fn, expected):
        v = verify_derivation_claims(
            f"M235 = 7518.44 and N235 = {expected:g}",
            "R235 | v=1\nCOLUMNS: Warehouse=M | Round=N\n"
            f"FORMULAS FOR THE MATCHED ROW(S): M235==7518.44 | N235=={fn}",
        )
        assert any(fv.status == VERIFIED_COMPUTED for fv in v.verdicts), v.summary()


class TestChainClaims:
    """A chain attributes its result to the LEFTMOST cell, and checks its arithmetic.

    RCA 2026-09-17 finding 6, reproduced by running the regex alone: the simple
    pattern, scanning left to right over "R235 = P235-K235 = 1893.7", skipped
    "R235 =" (no number followed) and then matched "K235 = 1893.7" — attributing
    the result to K235 and reporting a FALSE contradiction ("K235 evaluates to
    5625.3, not 1893.7") against a reply whose arithmetic was correct
    (7519 - 5625.3 = 1893.7 is R235's value).
    """

    BLOCK = (
        "R235 | LIST Price=7519.0 | Factory Price=5350 | Warehouse=5625.3\n"
        "COLUMNS: LIST Price=P | Factory Price=F | Warehouse=K\n"
        "FORMULAS FOR THE MATCHED ROW(S): P235==7519.0 | K235==5625.3 | R235==P235-K235"
    )

    def test_a_chain_belongs_to_its_leftmost_cell(self):
        from core.derivation_verification import extract_claims

        claims = extract_claims("R235 = P235-K235 = 1893.7")
        assert [(c.cell, c.claimed) for c in claims] == [("R235", 1893.7)], (
            "the result must be attributed to the leftmost cell, not the last "
            "cell named before the equals sign"
        )
        assert claims[0].expression.replace(" ", "") == "P235-K235"

    def test_a_correct_chain_is_verified_not_contradicted(self):
        v = verify_derivation_claims("R235 = P235-K235 = 1893.7", self.BLOCK)
        assert v.is_clean, v.summary()
        assert not v.contradicted, "a correct chain must not be called false"

    def test_a_chain_with_a_wrong_result_is_contradicted(self):
        v = verify_derivation_claims("R235 = P235-K235 = 9999", self.BLOCK)
        assert [fv.figure for fv in v.contradicted] == [9999.0]

    def test_a_chain_with_an_unavailable_dependency_is_unresolved(self):
        """Not wrong — unverifiable. The distinction the contract exists for."""
        v = verify_derivation_claims("R235 = P235-Z235 = 1893.7", self.BLOCK)
        assert not v.contradicted
        assert not v.is_clean
        assert "Z235" in v.verdicts[0].detail or "unavailable" in v.verdicts[0].detail

    def test_attributing_a_result_to_the_wrong_cell_is_caught(self):
        """The mirror case: K235 is 5625.3, so 1893.7 there IS wrong."""
        v = verify_derivation_claims("K235 = 1893.7", self.BLOCK)
        assert [fv.figure for fv in v.contradicted] == [1893.7]
        assert "5625.3" in v.contradicted[0].detail

    def test_a_claimed_assumption_is_not_reported_as_computed(self):
        """RCA finding 6: "O235 acts as a 1x multiplier" was never established.

        An unreferenced cell cannot be confirmed from the delivered window, so a
        reply resting on it must not come back clean.
        """
        v = verify_derivation_claims(
            "P235 = N235*O235 = 7519 and O235 = 1", self.BLOCK
        )
        assert not v.is_clean
