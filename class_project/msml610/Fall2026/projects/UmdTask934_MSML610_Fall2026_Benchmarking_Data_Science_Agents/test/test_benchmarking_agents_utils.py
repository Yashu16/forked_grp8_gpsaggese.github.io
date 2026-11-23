"""
Import as:

import test.test_benchmarking_agents_utils as ttbeagut
"""

import io
import logging
import os
import unittest.mock as umock
import urllib.error
import urllib.request
from typing import Any, Dict

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


# #############################################################################
# GAIA
# #############################################################################


class Test_load_gaia(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils.load_gaia()`.
    """

    def helper(self) -> pd.DataFrame:
        """
        Load the current test's local GAIA fixture.

        :return: scores table from the fixture
        """
        file_name = os.path.join(self.get_input_dir(), "gaia_results.json")
        source_url = (
            "https://huggingface.co/datasets/gaia-benchmark/results_public"
        )
        retrieved = "2026-11-20"
        df = bagutil.load_gaia(
            file_name, source_url=source_url, retrieved=retrieved
        )
        return df

    def test1(self) -> None:
        """
        Test both splits and all four difficulties, including provenance.
        """
        # Prepare outputs: each tuple is a published submission and its scores.
        submissions = [
            (
                "validation", "Example agent A", "Claude 3.7 Sonnet",
                "claude-3.7-sonnet", "2025-02-24", [0.4, 0.6, 0.3, 0.1],
            ),
            (
                "test", "Example agent B", "GPT 4.1",
                "gpt-4.1", "2025-04-14", [0.5, 0.7, 0.4, 0.2],
            ),
        ]
        difficulties = ["all", "level1", "level2", "level3"]
        records = []
        for split, agent, raw, model, date, scores in submissions:
            for difficulty, score in zip(difficulties, scores):
                records.append(
                    [
                        "gaia", split, agent, raw, model, "reasoning",
                        "accuracy", difficulty, score, float("nan"), date,
                        "https://huggingface.co/datasets/"
                        "gaia-benchmark/results_public",
                        "2026-11-20",
                    ]
                )
        expected = pd.DataFrame(records, columns=bagutil.SCHEMA_COLUMNS)
        # Run test.
        actual = self.helper()
        # Check outputs without imposing an ordering on the loader.
        sort_columns = ["agent", "difficulty"]
        actual = actual.sort_values(sort_columns).reset_index(drop=True)
        expected = expected.sort_values(sort_columns).reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected)

    def test2(self) -> None:
        """
        Test that GAIA scores stay fractions with their original precision.
        """
        # Prepare outputs.
        expected = 0.37575757
        # Run test.
        df = self.helper()
        actual = df.loc[df["difficulty"] == "all", "score"].tolist()
        # Check outputs.
        self.assertEqual(actual, [expected])

    def test3(self) -> None:
        """
        Test that an empty model family keeps all rows as "unknown".
        """
        # Prepare outputs.
        expected = [["", "unknown"]] * 4
        # Run test.
        df = self.helper()
        actual = df[["model_raw", "model"]].values.tolist()
        # Check outputs.
        self.assert_equal(str(actual), str(expected))

    def test4(self) -> None:
        """
        Test that null scores are logged and skipped while zero is retained.
        """
        # Prepare inputs.
        logger = "benchmarking_agents_utils"
        level = "DEBUG"
        # Prepare outputs.
        expected = {"all": 0.4, "level1": 0.0, "level3": 0.2}
        expected_info = "GAIA: loaded 3 score rows; skipped 5 null scores"
        # Run test.
        with self.assertLogs(logger, level=level) as logs:
            df = self.helper()
        actual = df.set_index("difficulty")["score"].to_dict()
        # Check outputs.
        self.assert_equal(str(actual), str(expected))
        messages = [record.getMessage() for record in logs.records]
        skipped = [
            message for message in messages if "Skipping null" in message
        ]
        self.assertEqual(len(skipped), 5)
        self.assert_equal(messages[-1], expected_info)

    def test5(self) -> None:
        """
        Test that empty input returns an empty table with schema columns.
        """
        # Prepare outputs.
        expected = bagutil.SCHEMA_COLUMNS
        # Run test.
        df = self.helper()
        # Check outputs.
        self.assertTrue(df.empty)
        self.assert_equal(str(list(df.columns)), str(expected))

    def test6(self) -> None:
        """
        Test that validation rejects percent-scale GAIA scores.
        """
        # Run test and check outputs.
        with self.assertRaises(AssertionError):
            self.helper()


# #############################################################################
# Test_slim_swe_bench
# #############################################################################


def _make_swe_bench_result(**overrides: Any) -> Dict[str, Any]:
    """
    Build one SWE-bench leaderboard result with every kept field.

    :param overrides: field values that replace the defaults
    :return: one result, as in `data/leaderboards.json`
    """
    result = {
        "name": "Gemini 3 Flash",
        "model_display": "Gemini 3 Flash",
        "agent": "mini-SWE-agent",
        "agent_org": "SWE-bench",
        "model_org": "Google",
        "date": "2026-02-13",
        "resolved": 72.7,
        "cost": 105.55,
        "instance_cost": 0.21,
        "os_model": False,
        "os_system": True,
        "checked": True,
        "folder": "20260213_mini-v2_gemini-3-flash",
    }
    result.update(overrides)
    return result


class Test_slim_swe_bench(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils.slim_swe_bench()`.
    """

    def test1(self) -> None:
        """
        Test that only the kept fields of each result stay.
        """
        # Prepare inputs.
        result = _make_swe_bench_result(logs="s3://logs", trajs="s3://trajs")
        data = {
            "leaderboards": [
                {"name": "Verified", "logo": "x.svg", "results": [result]}
            ]
        }
        # Run test.
        slim = bagutil.slim_swe_bench(data)
        # Check outputs.
        leaderboard = slim["leaderboards"][0]
        self.assertEqual(sorted(leaderboard), ["name", "results"])
        self.assertEqual(
            sorted(leaderboard["results"][0]),
            sorted(bagutil.SWE_BENCH_FIELDS),
        )

    def test2(self) -> None:
        """
        Test that a missing field stays missing, so the loader can flag it.
        """
        # Prepare inputs.
        result = _make_swe_bench_result()
        del result["cost"]
        data = {"leaderboards": [{"name": "Lite", "results": [result]}]}
        # Run test.
        slim = bagutil.slim_swe_bench(data)
        # Check outputs.
        self.assertNotIn("cost", slim["leaderboards"][0]["results"][0])


# #############################################################################
# Test_parse_gaia_page
# #############################################################################


def _make_gaia_page(*, partial: bool = False) -> Dict[str, Any]:
    """
    Build one page of the Hugging Face datasets-server `rows` response.

    :param partial: whether the server says the page is incomplete
    :return: a page with 2 GAIA rows
    """
    rows = []
    for idx, model in enumerate(["AgentIM", "Magentic-One"]):
        row = {
            "model": model,
            "model_family": "GPT-4-turbo",
            "system_prompt": "You are a helpful assistant.",
            "url": "",
            "organisation": "",
            "score": 0.37575757575757573,
            "score_level1": 0.5094339622641509,
            "score_level2": 0.36046511627906974,
            "score_level3": 0.15384615384615385,
            "date": "2024-05-26",
        }
        rows.append({"row_idx": idx, "row": row, "truncated_cells": []})
    page = {"rows": rows, "num_rows_total": 2, "partial": partial}
    return page


class Test_parse_gaia_page(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils.parse_gaia_page()`.
    """

    def test1(self) -> None:
        """
        Test that rows lose `system_prompt` and gain `split`.
        """
        # Prepare inputs.
        page = _make_gaia_page()
        # Run test.
        rows = bagutil.parse_gaia_page(page, split="validation")
        # Check outputs.
        self.assertEqual(len(rows), 2)
        self.assertNotIn("system_prompt", rows[0])
        self.assertEqual(rows[0]["split"], "validation")
        self.assertEqual(rows[1]["model"], "Magentic-One")
        self.assertAlmostEqual(rows[0]["score"], 0.37575757575757573)

    def test2(self) -> None:
        """
        Test that a page the server marks as partial is rejected.
        """
        # Prepare inputs.
        page = _make_gaia_page(partial=True)
        # Run test and check outputs.
        with self.assertRaises(AssertionError):
            bagutil.parse_gaia_page(page, split="test")


# #############################################################################
# Test_make_provenance_entry
# #############################################################################


class Test_make_provenance_entry(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils.make_provenance_entry()`.
    """

    def test1(self) -> None:
        """
        Test that the entry has the file's sha256 and echoes the source.
        """
        # Prepare inputs.
        file_name = os.path.join(self.get_input_dir(), "sample.txt")
        # Prepare outputs.
        expected = {
            "url": "https://example.com/data.json",
            "revision": "abc123",
            "retrieved": "2026-11-20",
            "sha256": (
                "ba7816bf8f01cfea414140de5dae2223"
                "b00361a396177a9cb410ff61f20015ad"
            ),
        }
        # Run test.
        actual = bagutil.make_provenance_entry(
            file_name,
            url="https://example.com/data.json",
            revision="abc123",
            retrieved="2026-11-20",
        )
        # Check outputs.
        self.assertEqual(actual, expected)


# #############################################################################
# Test__download_json
# #############################################################################


def _http_error(code: int) -> urllib.error.HTTPError:
    """
    Build the error `urllib` raises for an HTTP status code.

    :param code: HTTP status code
    :return: the error
    """
    error = urllib.error.HTTPError(
        "https://example.com/data.json", code, "error", {}, None
    )
    return error


class Test__download_json(hunitest.TestCase):
    """
    Test `benchmarking_agents_utils._download_json()`.

    The network is replaced by a fake `urlopen`, so no request is made.
    """

    def test1(self) -> None:
        """
        Test that a temporary server error (502) is retried.
        """
        # Prepare inputs.
        response = io.BytesIO(b'{"rows": []}')
        side_effect = [_http_error(502), response]
        # Run test.
        with umock.patch.object(
            urllib.request, "urlopen", side_effect=side_effect
        ) as urlopen:
            data = bagutil._download_json(
                "https://example.com/data.json", wait_in_secs=0.0
            )
        # Check outputs.
        self.assertEqual(data, {"rows": []})
        self.assertEqual(urlopen.call_count, 2)

    def test2(self) -> None:
        """
        Test that a client error (404) fails at once, without retrying.
        """
        # Prepare inputs.
        side_effect = [_http_error(404)]
        # Run test and check outputs.
        with umock.patch.object(
            urllib.request, "urlopen", side_effect=side_effect
        ) as urlopen:
            with self.assertRaises(urllib.error.HTTPError):
                bagutil._download_json(
                    "https://example.com/data.json", wait_in_secs=0.0
                )
        self.assertEqual(urlopen.call_count, 1)

    def test3(self) -> None:
        """
        Test that the last error is raised once every attempt failed.
        """
        # Prepare inputs.
        side_effect = [_http_error(503)] * 3
        # Run test and check outputs.
        with umock.patch.object(
            urllib.request, "urlopen", side_effect=side_effect
        ) as urlopen:
            with self.assertRaises(urllib.error.HTTPError):
                bagutil._download_json(
                    "https://example.com/data.json",
                    n_attempts=3,
                    wait_in_secs=0.0,
                )
        self.assertEqual(urlopen.call_count, 3)
