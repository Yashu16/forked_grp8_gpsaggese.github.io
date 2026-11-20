"""
Helper functions for the Benchmarking Data Science Agents project.

Used by the 2 notebooks and by `fetch_leaderboards.py`:
- The unified scores table: its columns and the checks every row must pass
- Model name normalization

Import as:

import benchmarking_agents_utils as bagutil
"""

import logging
import re
from typing import List

import pandas as pd

import helpers.hdbg as hdbg

_LOG = logging.getLogger(__name__)


# #############################################################################
# Schema
# #############################################################################


# Columns of the unified scores table, in order. The table is in long format:
# one row per (submission, difficulty).
SCHEMA_COLUMNS: List[str] = [
    "benchmark",
    "split",
    "agent",
    "model_raw",
    "model",
    "task_type",
    "metric",
    "difficulty",
    "score",
    "cost_usd",
    "date",
    "source_url",
    "retrieved",
]

# Benchmarks that the table can hold (PR 2 extends this set).
BENCHMARKS: List[str] = ["swe_bench", "gaia"]

# Format of the `date` and `retrieved` columns.
_DATE_FORMAT = "%Y-%m-%d"


def _dassert_dates(df: pd.DataFrame, col: str) -> None:
    """
    Check that every value of a column is an ISO `YYYY-MM-DD` date.

    :param df: scores table
    :param col: name of the column to check
    """
    dates = pd.to_datetime(df[col], format=_DATE_FORMAT, errors="coerce")
    bad = df.loc[dates.isna(), col].tolist()
    hdbg.dassert(
        not bad,
        "Column '%s' has values that are not %s dates: %s",
        col,
        _DATE_FORMAT,
        bad[:5],
    )


def validate_scores(df: pd.DataFrame) -> None:
    """
    Check that a scores table follows the schema, and raise otherwise.

    The checks are:
    - the columns are `SCHEMA_COLUMNS`, in order
    - `benchmark` is one of `BENCHMARKS`
    - `score` is a fraction in [0, 1], with no NaN
    - `date` and `retrieved` are `YYYY-MM-DD` dates
    - `source_url` is never empty

    :param df: scores table
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    hdbg.dassert_eq(list(df.columns), SCHEMA_COLUMNS)
    hdbg.dassert_is_subset(set(df["benchmark"]), set(BENCHMARKS))
    # A score above 1 is usually a percent that was not divided by 100.
    score = pd.to_numeric(df["score"], errors="coerce")
    bad = df.loc[score.isna() | (score < 0) | (score > 1), "score"].tolist()
    hdbg.dassert(
        not bad,
        "Column 'score' must be a fraction in [0, 1] with no NaN, got: %s",
        bad[:5],
    )
    _dassert_dates(df, "date")
    _dassert_dates(df, "retrieved")
    source_url = df["source_url"].fillna("").astype(str).str.strip()
    n_empty = int((source_url == "").sum())
    hdbg.dassert_eq(
        n_empty, 0, "Column 'source_url' has %s empty values", n_empty
    )


# #############################################################################
# Model names
# #############################################################################


def normalize_model_name(name: str) -> str:
    """
    Turn a model name into a lowercase id that can be matched across
    benchmarks.

    E.g., "Claude 3.7 Sonnet" becomes "claude-3.7-sonnet". A blank name
    becomes "unknown". A curated alias map is added on top of this in PR 2.

    :param name: model name as published on a leaderboard
    :return: normalized model name
    """
    hdbg.dassert_isinstance(name, str)
    normalized = re.sub(r"[^a-z0-9.]+", "-", name.lower()).strip("-")
    if not normalized:
        normalized = "unknown"
    return normalized
