"""
Helper functions for the Benchmarking Data Science Agents project.

Used by the 2 notebooks and by `fetch_leaderboards.py`:
- The unified scores table: its columns and the checks every row must pass
- Model name normalization
- Loaders that turn each leaderboard snapshot into rows of the table
- Building the table from the snapshots
- Downloading the leaderboard snapshots and recording where they came from

Import as:

import benchmarking_agents_utils as bagutil
"""

import datetime
import gzip
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
# SWE-bench
# #############################################################################


def load_swe_bench(
    file_name: str, *, source_url: str, retrieved: str
) -> pd.DataFrame:
    """
    Load slim SWE-bench leaderboard JSON into the unified scores schema.

    :param file_name: path to the slim leaderboard JSON file
    :param source_url: URL of the published leaderboard snapshot
    :param retrieved: date the snapshot was retrieved, in `YYYY-MM-DD` format
    :return: leaderboard results using `SCHEMA_COLUMNS`
    """
    payload = hio.from_json(file_name)
    rows: List[Dict[str, Any]] = []
    for leaderboard in payload["leaderboards"]:
        split = leaderboard["name"].lower()
        for result in leaderboard["results"]:
            for key in ["resolved", "date", "agent"]:
                hdbg.dassert(
                    key in result,
                    "SWE-bench result is missing required key '%s'",
                    key,
                )
            model_raw = result.get("model_display") or result.get("name", "")
            rows.append(
                {
                    "benchmark": "swe_bench",
                    "split": split,
                    "agent": result["agent"],
                    "model_raw": model_raw,
                    "model": normalize_model_name(model_raw),
                    "task_type": "coding",
                    "metric": "resolved_rate",
                    "difficulty": "all",
                    "score": result["resolved"] / 100,
                    "cost_usd": result.get("cost", float("nan")),
                    "date": result["date"],
                    "source_url": source_url,
                    "retrieved": retrieved,
                }
            )
    df = pd.DataFrame(rows, columns=SCHEMA_COLUMNS)
    validate_scores(df)
    return df


# #############################################################################
# GAIA
# #############################################################################


def load_gaia(
    file_name: str, *, source_url: str, retrieved: str
) -> pd.DataFrame:
    """
    Load a local GAIA snapshot into the unified scores schema.

    Each submission yields up to four rows: `all`, `level1`, `level2`,
    and `level3`. Scores are already fractions, so no scaling is applied.
    Null scores are skipped; an empty `model_family` is kept as an unknown
    model. Duplicate submissions are left for `build_scores_table()`.

    :param file_name: JSON list of submissions saved by `fetch_gaia()`
    :param source_url: source URL recorded for the snapshot
    :param retrieved: snapshot retrieval date, as `YYYY-MM-DD`
    :return: validated scores table with `SCHEMA_COLUMNS` in order
    """
    _LOG.debug("Loading GAIA snapshot '%s'", file_name)
    data = _from_json(file_name)
    hdbg.dassert_isinstance(data, list, "GAIA snapshot must be a list")
    score_columns = {
        "score": "all",
        "score_level1": "level1",
        "score_level2": "level2",
        "score_level3": "level3",
    }
    required = ["split", "model", "model_family", "date"] + list(score_columns)
    rows: List[Dict[str, Any]] = []
    n_null = 0
    for row_index, submission in enumerate(data):
        # Missing fields indicate a changed snapshot format, not null scores.
        hdbg.dassert_isinstance(submission, dict, "GAIA row must be a dict")
        for field in required:
            hdbg.dassert_in(
                field,
                submission,
                "GAIA row %s is missing '%s'",
                row_index,
                field,
            )
        hdbg.dassert_in(
            submission["split"], ["validation", "test"], "Invalid GAIA split"
        )
        model_raw = submission["model_family"]
        model = normalize_model_name(model_raw)
        for column, difficulty in score_columns.items():
            score = submission[column]
            if pd.isna(score):
                _LOG.debug(
                    "Skipping null GAIA score '%s' for row '%s'",
                    column,
                    row_index,
                )
                n_null += 1
                continue
            # Preserve the published system name separately from its base model.
            rows.append(
                {
                    "benchmark": "gaia",
                    "split": submission["split"],
                    "agent": submission["model"],
                    "model_raw": model_raw,
                    "model": model,
                    "task_type": "reasoning",
                    "metric": "accuracy",
                    "difficulty": difficulty,
                    "score": score,
                    "cost_usd": float("nan"),
                    "date": submission["date"],
                    "source_url": source_url,
                    "retrieved": retrieved,
                }
            )
    # Explicit columns also preserve the schema for an empty snapshot.
    df = pd.DataFrame(rows, columns=SCHEMA_COLUMNS)
    validate_scores(df)
    _LOG.info(
        "GAIA: loaded %s score rows; skipped %s null scores", len(df), n_null
    )
    return df


# #############################################################################
# Table build
# #############################################################################


def _from_json(file_name: str) -> Any:
    """
    Read a JSON file, gzipped if its name ends in `.gz`.

    :param file_name: path of the file
    :return: the parsed JSON
    """
    if file_name.endswith(".gz"):
        with gzip.open(file_name, "rt", encoding="utf-8") as file:
            data = json.load(file)
    else:
        with open(file_name, encoding="utf-8") as file:
            data = json.load(file)
    return data


def _to_json_gz(file_name: str, obj: Any) -> None:
    """
    Write an object as gzipped JSON, with the same bytes for the same object.

    The gzip header normally holds the write time. It's set to 0 so that the
    sha256 in `provenance.json` only changes when the data changes.

    :param file_name: path of the file to write, ending in `.json.gz`
    :param obj: object to write
    """
    hdbg.dassert(file_name.endswith(".json.gz"), "Bad name '%s'", file_name)
    hio.create_dir(os.path.dirname(file_name), incremental=True)
    txt = json.dumps(obj, indent=4)
    with open(file_name, "wb") as file:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=file, compresslevel=9, mtime=0
        ) as gz_file:
            gz_file.write(txt.encode("utf-8"))


def _file_sha256(file_name: str) -> str:
    """
    Return the sha256 of a file's bytes, as a hex string.

    :param file_name: path of the file
    :return: sha256 hex digest
    """
    with open(file_name, "rb") as file:
        sha256 = hashlib.sha256(file.read()).hexdigest()
    return sha256


def build_scores_table(raw_dir: str) -> pd.DataFrame:
    """
    Build the unified scores table from the raw snapshots in a directory.

    The function:
    - checks that each snapshot's sha256 matches `provenance.json`, so a file
      edited after the download is caught
    - loads each snapshot, stamping its rows with the file's URL and download
      date
    - drops exact duplicate rows, sorts the rows and validates the table

    :param raw_dir: directory with `SWE_BENCH_FILE`, `GAIA_FILE` and
        `PROVENANCE_FILE`
    :return: scores table with `SCHEMA_COLUMNS`
    """
    loaders = {SWE_BENCH_FILE: load_swe_bench, GAIA_FILE: load_gaia}
    provenance = hio.from_json(os.path.join(raw_dir, PROVENANCE_FILE))
    hdbg.dassert_eq(sorted(provenance), sorted(loaders))
    dfs = []
    for file_name, loader in loaders.items():
        entry = provenance[file_name]
        path = os.path.join(raw_dir, file_name)
        sha256 = _file_sha256(path)
        hdbg.dassert_eq(
            sha256,
            entry["sha256"],
            "The sha256 of '%s' doesn't match '%s': the file changed after "
            "the download",
            file_name,
            PROVENANCE_FILE,
        )
        df = loader(path, source_url=entry["url"], retrieved=entry["retrieved"])
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)
    # Drop exact duplicates only: distinct submissions of a model all stay.
    n_rows = len(df)
    df = df.drop_duplicates()
    _LOG.info("Dropped %s exact duplicate rows", n_rows - len(df))
    df = df.sort_values(["benchmark", "split", "date", "agent"], kind="stable")
    df = df.reset_index(drop=True)
    validate_scores(df)
    _LOG.info(
        "Scores table: %s rows (%s)",
        len(df),
        df["benchmark"].value_counts().to_dict(),
    )
    return df


# #############################################################################
# Fetch
# #############################################################################


# Commit of `SWE-bench/swe-bench.github.io` to read `data/leaderboards.json`
# from.
SWE_BENCH_SITE_SHA = "193160a463a435d05cf44a1fa9dc5eac832113c3"
# Revision of the Hugging Face dataset `gaia-benchmark/results_public` that we
# expect. The datasets-server only serves the latest revision, so
# `fetch_gaia()` records the revision it actually got.
GAIA_REVISION = "4b950a33b8d76784ea3dc2e660c7823a0fde03c0"

# Names of the raw snapshot files.
SWE_BENCH_FILE = "swe_bench_leaderboards.json"
# The GAIA snapshot and the scores table are gzipped to stay under the repo's
# 500 KB limit per file.
GAIA_FILE = "gaia_results.json.gz"
PROVENANCE_FILE = "provenance.json"
SCORES_FILE = "scores.csv.gz"

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
    entry = {
        "url": url,
        "revision": revision,
        "retrieved": retrieved,
        "sha256": _file_sha256(file_name),
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
    _to_json_gz(file_name, rows)
    url = _GAIA_SOURCE_URL.format(
        dataset=_GAIA_DATASET, revision=served, config=_GAIA_CONFIG
    )
    entry = make_provenance_entry(
        file_name, url=url, revision=served, retrieved=_today()
    )
    return entry
