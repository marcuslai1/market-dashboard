"""Masthead provenance line — the run time comes from the report, not a constant."""
from components.masthead import SCHEDULED_RUN_SGT, run_time_sgt


def test_run_time_is_read_from_generated_at():
    assert run_time_sgt({"generated_at": "2026-10-01T12:05:33.779853"}) == "12:05"
    assert run_time_sgt({"generated_at": "2026-09-14T13:41:02"}) == "13:41"


def test_run_time_falls_back_to_the_schedule():
    assert SCHEDULED_RUN_SGT == "12:05"
    for meta in (None, {}, {"generated_at": ""}, {"generated_at": "not a time"}):
        assert run_time_sgt(meta) == "12:05", meta
