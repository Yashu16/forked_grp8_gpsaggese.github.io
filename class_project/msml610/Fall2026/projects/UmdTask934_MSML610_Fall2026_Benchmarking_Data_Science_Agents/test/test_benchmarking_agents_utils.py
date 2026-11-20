"""
Import as:

import test.test_benchmarking_agents_utils as ttbeagut
"""

import logging
from typing import Any

import pandas as pd

import helpers.hunit_test as hunitest

import benchmarking_agents_utils as bagutil

_LOG = logging.getLogger(__name__)


# #############################################################################
# Helpers
# #############################################################################


def _make_row(**overrides: Any) -> pd.DataFrame:
    """
    Build a one-row scores table with valid defaults.

    :param overrides: column values that replace the defaults
    :return: a one-row dataframe with `SCHEMA_COLUMNS` in order
    """
    row = {
        "benchmark": "swe_bench",
        "split": "verified",
        "agent": "mini-SWE-agent",
        "model_raw": "Claude 3.7 Sonnet",
        "model": "claude-3.7-sonnet",
        "task_type": "coding",
        "metric": "resolved_rate",
        "difficulty": "all",
        "score": 0.5,
        "cost_usd": float("nan"),
        "date": "2025-02-24",
        "source_url": "https://example.com/leaderboards.json",
        "retrieved": "2026-11-16",
    }
    row.update(overrides)
    df = pd.DataFrame([row], columns=bagutil.SCHEMA_COLUMNS)
    return df


# #############################################################################
# Test_normalize_model_name
# #############################################################################


class Test_normalize_model_name(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils.normalize_model_name()`.
    """

    def test1(self) -> None:
        """
        Test that a display name becomes lowercase with dashes.
        """
        # Prepare inputs.
        name = "Claude 3.7 Sonnet"
        # Prepare outputs.
        expected = "claude-3.7-sonnet"
        # Run test.
        actual = bagutil.normalize_model_name(name)
        # Check outputs.
        self.assert_equal(actual, expected)

    def test2(self) -> None:
        """
        Test that a blank name becomes "unknown".
        """
        # Prepare inputs.
        name = "  "
        # Prepare outputs.
        expected = "unknown"
        # Run test.
        actual = bagutil.normalize_model_name(name)
        # Check outputs.
        self.assert_equal(actual, expected)


# #############################################################################
# Test_validate_scores
# #############################################################################


class Test_validate_scores(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils.validate_scores()`.
    """

    def test1(self) -> None:
        """
        Test that a valid row passes.
        """
        # Prepare inputs.
        df = _make_row(score=0.5)
        # Run test.
        bagutil.validate_scores(df)

    def test2(self) -> None:
        """
        Test that a percent-scale score is rejected.
        """
        # Prepare inputs.
        df = _make_row(score=72.7)
        # Run test and check outputs.
        with self.assertRaises(AssertionError):
            bagutil.validate_scores(df)

    def test3(self) -> None:
        """
        Test that an empty `source_url` is rejected.
        """
        # Prepare inputs.
        df = _make_row(source_url="")
        # Run test and check outputs.
        with self.assertRaises(AssertionError):
            bagutil.validate_scores(df)
