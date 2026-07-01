"""Regression tests for the legacy writeup shim (P1-3).

548 report entries still use the legacy `signal_rationale` string instead of the
new `writeup` dict, so `_writeup_for_render` / `_legacy_rationale_from` must keep
handling both. Lock that behavior.
"""
from lib.formatters import _legacy_rationale_from, _writeup_for_render


def test_new_writeup_dict_passthrough():
    d = {"writeup": {"headline": "H", "what_to_do": "Do X",
                     "prior_period_delta_narrative": "Delta"}}
    out = _writeup_for_render(d)
    assert out["headline"] == "H"
    assert out["what_to_do"] == "Do X"
    assert out["prior_period_delta_narrative"] == "Delta"


def test_legacy_rationale_splits_headline_and_body():
    d = {"signal": "BUY", "signal_rationale": "First sentence. Then the rest here."}
    out = _writeup_for_render(d)
    assert out["headline"] == "First sentence."
    assert out["what_to_do"] == "Then the rest here."


def test_legacy_single_sentence_has_no_what_to_do():
    d = {"signal": "BUY", "signal_rationale": "Only one sentence."}
    out = _writeup_for_render(d)
    assert out["headline"] == "Only one sentence."
    assert out["what_to_do"] is None


def test_legacy_hold_suppresses_what_to_do():
    d = {"signal": "HOLD", "signal_rationale": "Context. More context."}
    assert _writeup_for_render(d)["what_to_do"] is None


def test_legacy_caution_hard_block_suppresses_what_to_do():
    d = {"signal": "CAUTION", "caution_source": "hard_block",
         "signal_rationale": "Blocked. Extra."}
    assert _writeup_for_render(d)["what_to_do"] is None


def test_legacy_rationale_from_new_schema_concatenates():
    d = {"writeup": {"headline": "H", "prior_period_delta_narrative": "D",
                     "what_to_do": "W"}}
    assert _legacy_rationale_from(d) == "H D W"


def test_legacy_rationale_from_legacy_field():
    assert _legacy_rationale_from({"signal_rationale": "Legacy text."}) == "Legacy text."
