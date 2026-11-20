"""
Helper functions for the Benchmarking Data Science Agents project.

Used by the 2 notebooks and by `fetch_leaderboards.py`:
- The unified scores table: its columns and the checks every row must pass
- Model name normalization
- Downloading the leaderboard snapshots and recording where they came from

Import as:

import benchmarking_agents_utils as bagutil
"""

import datetime
import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

import pandas as pd

import helpers.hdbg as hdbg
import helpers.hio as hio

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


# #############################################################################
# Fetch
# #############################################################################


# Commit of `SWE-bench/swe-bench.github.io` to read `data/leaderboards.json`
# from.
SWE_BENCH_SITE_SHA = "193160a463a435d05cf44a1fa9dc5eac832113c3"
# Revision of the Hugging Face dataset `gaia-benchmark/results_public` that we
# expect. The datasets-server only serves the latest revision, so
# `fetch_gaia()` records the revision it actually got.
GAIA_REVISION = "a1f6489aea6808003b35465341a3cbcb84f15c82"

# Names of the raw snapshot files.
SWE_BENCH_FILE = "swe_bench_leaderboards.json"
GAIA_FILE = "gaia_results.json"
PROVENANCE_FILE = "provenance.json"

# Fields kept for each SWE-bench result. The others (logs, trajectories,
# per-task details) are large and not needed.
SWE_BENCH_FIELDS: List[str] = [
    "name",
    "model_display",
    "agent",
    "agent_org",
    "model_org",
    "date",
    "resolved",
    "cost",
    "instance_cost",
    "os_model",
    "os_system",
    "checked",
    "folder",
]

# GAIA splits to download.
GAIA_SPLITS: List[str] = ["validation", "test"]

_SWE_BENCH_URL = (
    "https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/"
    "{sha}/data/leaderboards.json"
)
_GAIA_DATASET = "gaia-benchmark/results_public"
_GAIA_CONFIG = "2023"
_GAIA_ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset={dataset}"
    "&config={config}&split={split}&offset={offset}&length={length}"
)
_GAIA_API_URL = "https://huggingface.co/api/datasets/{dataset}"
_GAIA_SOURCE_URL = (
    "https://huggingface.co/datasets/{dataset}/tree/{revision}/{config}"
)
# Largest page the datasets-server returns.
_GAIA_PAGE_LENGTH = 100
# Pause between 2 page requests, to stay under the datasets-server rate limit.
_GAIA_PAGE_WAIT_IN_SECS = 1.0
_TIMEOUT_IN_SECS = 60


def _is_temporary_error(error: Exception) -> bool:
    """
    Return whether a download error is worth retrying.

    Server errors (5xx), rate limits (429), timeouts and dropped connections
    are temporary. Other HTTP errors (e.g., 404) are not.

    :param error: error raised by `urllib.request.urlopen()`
    :return: whether to retry
    """
    if isinstance(error, urllib.error.HTTPError):
        is_temporary = error.code >= 500 or error.code == 429
    else:
        is_temporary = isinstance(error, (urllib.error.URLError, TimeoutError))
    return is_temporary


def _download_json(
    url: str, *, n_attempts: int = 5, wait_in_secs: float = 5.0
) -> Any:
    """
    Download a URL and parse it as JSON, retrying temporary errors.

    :param url: URL to download
    :param n_attempts: number of attempts before giving up
    :param wait_in_secs: wait before the first retry, doubled at each retry
    :return: the parsed JSON
    """
    hdbg.dassert_lte(1, n_attempts)
    for attempt in range(1, n_attempts + 1):
        _LOG.debug("Downloading %s (attempt %s)", url, attempt)
        try:
            with urllib.request.urlopen(
                url, timeout=_TIMEOUT_IN_SECS
            ) as response:
                data = json.load(response)
            return data
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == n_attempts or not _is_temporary_error(error):
                raise
            wait = wait_in_secs * 2 ** (attempt - 1)
            _LOG.warning(
                "Download failed (%s), retrying in %s s: %s", error, wait, url
            )
            time.sleep(wait)
    # Not reachable: the loop either returns or raises.
    hdbg.dfatal(f"Could not download {url}")


def _today() -> str:
    """
    Return today's date in UTC, as `YYYY-MM-DD`.
    """
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    return today


def slim_swe_bench(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep only the leaderboard names and the `SWE_BENCH_FIELDS` of each result.

    A field missing from a result stays missing, so the loader can report it.

    :param data: content of `data/leaderboards.json`
    :return: the same structure with only the kept fields
    """
    hdbg.dassert_in("leaderboards", data)
    leaderboards = []
    for leaderboard in data["leaderboards"]:
        results = []
        for result in leaderboard["results"]:
            kept = {k: result[k] for k in SWE_BENCH_FIELDS if k in result}
            results.append(kept)
        leaderboards.append({"name": leaderboard["name"], "results": results})
    slim = {"leaderboards": leaderboards}
    return slim


def parse_gaia_page(page: Dict[str, Any], *, split: str) -> List[Dict[str, Any]]:
    """
    Turn one page of the datasets-server `rows` response into GAIA rows.

    Each row loses `system_prompt` (long and not needed) and gains `split`.

    :param page: parsed JSON of one `rows` request
    :param split: GAIA split the page belongs to (e.g., "validation")
    :return: one dict per row
    """
    hdbg.dassert(not page["partial"], "The server returned a partial page")
    rows = []
    for item in page["rows"]:
        # Only `system_prompt` may be cut short by the server, and it's dropped.
        truncated = set(item["truncated_cells"]) - {"system_prompt"}
        hdbg.dassert(
            not truncated,
            "Row %s has truncated cells: %s",
            item["row_idx"],
            truncated,
        )
        row = {k: v for k, v in item["row"].items() if k != "system_prompt"}
        row["split"] = split
        rows.append(row)
    return rows


def make_provenance_entry(
    file_name: str, *, url: str, revision: str, retrieved: str
) -> Dict[str, str]:
    """
    Describe where a raw snapshot file came from.

    The sha256 lets `build_scores_table()` detect a file edited after the
    download.

    :param file_name: path of the saved snapshot
    :param url: URL the data was downloaded from
    :param revision: commit or dataset revision of the data
    :param retrieved: download date, as `YYYY-MM-DD`
    :return: dict with `url`, `revision`, `retrieved` and `sha256`
    """
    with open(file_name, "rb") as file:
        sha256 = hashlib.sha256(file.read()).hexdigest()
    entry = {
        "url": url,
        "revision": revision,
        "retrieved": retrieved,
        "sha256": sha256,
    }
    return entry


def fetch_swe_bench(dst_dir: str, *, sha: str) -> Dict[str, str]:
    """
    Download the SWE-bench leaderboards at a commit and save a slim copy.

    :param dst_dir: directory to save `SWE_BENCH_FILE` into
    :param sha: commit of `SWE-bench/swe-bench.github.io`
    :return: provenance entry of the saved file
    """
    url = _SWE_BENCH_URL.format(sha=sha)
    data = slim_swe_bench(_download_json(url))
    n_results = sum(len(lb["results"]) for lb in data["leaderboards"])
    _LOG.info(
        "SWE-bench: %s leaderboards, %s results",
        len(data["leaderboards"]),
        n_results,
    )
    file_name = os.path.join(dst_dir, SWE_BENCH_FILE)
    hio.to_json(file_name, data)
    entry = make_provenance_entry(
        file_name, url=url, revision=sha, retrieved=_today()
    )
    return entry


def _get_gaia_revision() -> str:
    """
    Return the current revision of the GAIA results dataset on Hugging Face.
    """
    info = _download_json(_GAIA_API_URL.format(dataset=_GAIA_DATASET))
    revision = info["sha"]
    return revision


def fetch_gaia(dst_dir: str, *, revision: str) -> Dict[str, str]:
    """
    Download every GAIA results row of `GAIA_SPLITS` and save them.

    The datasets-server only serves the latest revision of the dataset. So the
    function warns if that differs from `revision`, records the revision it
    actually got, and fails if the dataset changes during the download.

    :param dst_dir: directory to save `GAIA_FILE` into
    :param revision: revision of the dataset that is expected
    :return: provenance entry of the saved file
    """
    served = _get_gaia_revision()
    if served != revision:
        _LOG.warning(
            "GAIA results are at revision %s, not the expected %s: "
            "saving revision %s",
            served,
            revision,
            served,
        )
    rows: List[Dict[str, Any]] = []
    for split in GAIA_SPLITS:
        offset = 0
        n_total = None
        while n_total is None or offset < n_total:
            url = _GAIA_ROWS_URL.format(
                dataset=_GAIA_DATASET,
                config=_GAIA_CONFIG,
                split=split,
                offset=offset,
                length=_GAIA_PAGE_LENGTH,
            )
            if offset > 0:
                time.sleep(_GAIA_PAGE_WAIT_IN_SECS)
            page = _download_json(url)
            n_total = page["num_rows_total"]
            page_rows = parse_gaia_page(page, split=split)
            hdbg.dassert_lt(0, len(page_rows), "Empty page at offset %s", offset)
            rows.extend(page_rows)
            offset += len(page_rows)
        _LOG.info("GAIA %s: %s rows", split, n_total)
    hdbg.dassert_eq(
        _get_gaia_revision(),
        served,
        "The GAIA dataset changed during the download: run it again",
    )
    file_name = os.path.join(dst_dir, GAIA_FILE)
    hio.to_json(file_name, rows)
    url = _GAIA_SOURCE_URL.format(
        dataset=_GAIA_DATASET, revision=served, config=_GAIA_CONFIG
    )
    entry = make_provenance_entry(
        file_name, url=url, revision=served, retrieved=_today()
    )
    return entry
