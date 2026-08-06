"""Tests for ecd_validate.py, the pre-release data validator.

These guard the two defects that made the shipped copy abort instead of report:
a query error escaping as a duckdb exception rather than a RuntimeError, and an
uncast TIMESTAMPTZ, which duckdb cannot hand back to Python without pytz. The
validate-release workflow installs polars, duckdb and requests only, so the
executive check crashed the whole run.
"""

import datetime as dt
import importlib.util
import pathlib
import sys

import polars as pl
import pytest

duckdb = pytest.importorskip("duckdb")

ROOT = pathlib.Path(__file__).resolve().parent


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "ecd_validate", ROOT / "ecd_validate.py")
    module = importlib.util.module_from_spec(spec)
    # register before exec: the module defines dataclasses, and @dataclass
    # resolves annotations through sys.modules[cls.__module__]
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def validator():
    return load_validator()


@pytest.fixture(scope="module")
def tz_parquet(tmp_path_factory):
    """A file shaped like a country asset: `date` is Datetime with a zone."""
    path = tmp_path_factory.mktemp("assets") / "utopia.parquet"
    pl.DataFrame({
        "executive": ["A. Leader", "A. Leader", "B. Successor"],
        "date": [dt.datetime(2020, 1, 1), dt.datetime(2021, 1, 1),
                 dt.datetime(2022, 1, 1)],
    }).with_columns(
        pl.col("date").dt.replace_time_zone("UTC")
    ).write_parquet(path)
    return path


def test_sql_wraps_failures_in_runtime_error(validator, tz_parquet):
    """Callers catch RuntimeError to skip a file; anything else aborts the run."""
    engine = validator.Engine()
    with pytest.raises(RuntimeError):
        engine.sql("SELECT no_such_column FROM {t}", tz_parquet)


def test_executive_query_survives_a_zoned_date(validator, tz_parquet):
    """Reproduces the crash: duckdb needs pytz to return a TIMESTAMPTZ."""
    engine = validator.Engine()
    rep = validator.Report()
    validator.check_executives({"utopia": tz_parquet}, rep, engine)
    # No exception, and the check actually ran rather than being skipped.
    assert engine.sql(
        "SELECT min(date::TIMESTAMP) FROM {t}", tz_parquet)[0][0] is not None


def _executives(tmp_path, rows):
    path = tmp_path / "country.parquet"
    pl.DataFrame(
        {"executive": [r[0] for r in rows],
         "date": [dt.datetime.fromisoformat(r[1]) for r in rows]}
    ).with_columns(pl.col("date").dt.replace_time_zone("UTC")).write_parquet(path)
    return path


def _findings(validator, path, check):
    engine, rep = validator.Engine(), validator.Report()
    validator.check_executives({"country": path}, rep, engine)
    return [f for f in rep.findings if f.check == check]


def test_non_contiguous_terms_are_not_an_overlap(validator, tmp_path):
    """A leader with two terms encloses their successor without overlapping them.

    This is the Lars Lokke Rasmussen / Netanyahu / Putin shape. Comparing min and
    max alone reported it as a mis-attribution; nine of the fifteen overlaps in
    release 1.0.0 were this and nothing else.
    """
    path = _executives(tmp_path, [
        ("A. Returner", "2009-04-07"), ("A. Returner", "2011-10-03"),
        ("B. Interim", "2011-10-04"), ("B. Interim", "2015-06-27"),
        ("A. Returner", "2015-06-28"), ("A. Returner", "2019-06-27"),
    ])
    assert _findings(validator, path, "executive.term_overlap") == []
    assert _findings(validator, path, "executive.span_encloses")


def test_genuine_overlap_is_still_reported(validator, tmp_path):
    """Two people credited with documents across the same months."""
    path = _executives(tmp_path, [
        ("C. Incumbent", "2020-01-01"), ("C. Incumbent", "2020-03-15"),
        ("C. Incumbent", "2020-04-10"), ("C. Incumbent", "2020-06-01"),
        ("D. Successor", "2020-02-01"), ("D. Successor", "2020-05-01"),
        ("D. Successor", "2020-12-01"),
    ])
    assert _findings(validator, path, "executive.term_overlap")


def test_handover_day_is_not_an_overlap(validator, tmp_path):
    """Both leaders legitimately have documents on the day office changes hands.

    33 of Gerald R. Ford's rows are dated 1977-01-20, Carter's inauguration.
    His span reaches 1996 because of a convention speech, so the window is wide
    even though the only date he shares with Carter is the handover itself.
    """
    path = _executives(tmp_path, [
        ("E. Outgoing", "1974-08-09"), ("E. Outgoing", "1977-01-20"),
        ("E. Outgoing", "1996-08-12"),
        ("F. Incoming", "1977-01-20"), ("F. Incoming", "1981-01-19"),
    ])
    assert _findings(validator, path, "executive.term_overlap") == []
    assert _findings(validator, path, "executive.handover_day")


def test_alternating_terms_are_not_an_overlap(validator, tmp_path):
    """Two leaders who each hold office twice, in turn.

    Italy: Berlusconi 2001-2006 and 2008-2011, Prodi 1996-1998 and 2006-2008.
    Both have documents inside the other's span, but the dates never interleave.
    """
    path = _executives(tmp_path, [
        ("G. First", "1996-05-18"), ("G. First", "1998-10-20"),
        ("H. Second", "2001-06-12"), ("H. Second", "2006-05-12"),
        ("G. First", "2006-05-18"), ("G. First", "2008-04-24"),
        ("H. Second", "2008-05-08"), ("H. Second", "2011-11-12"),
    ])
    assert _findings(validator, path, "executive.term_overlap") == []
    assert _findings(validator, path, "executive.alternating_terms")
