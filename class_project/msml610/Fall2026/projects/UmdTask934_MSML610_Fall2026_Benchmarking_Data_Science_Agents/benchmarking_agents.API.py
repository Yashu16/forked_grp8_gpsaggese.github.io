# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Benchmark Leaderboards API Overview
#
# This notebook demonstrates the local API for combining SWE-bench and GAIA
# leaderboard results. It uses small offline fixtures for the loaders and the
# committed snapshots to build the complete scores table.

# %% [markdown]
# ## Imports and paths

# %%
import logging
import os

import pandas as pd

import helpers.hdbg as hdbg
import helpers.hnotebook as hnotebook

import benchmarking_agents_utils as bagutil

_LOG = logging.getLogger(__name__)
hdbg.init_logger(verbosity=logging.INFO)
hnotebook.config_notebook()

try:
    from IPython.display import display
except ImportError:
    display = print  # type: ignore

project_dir = os.getcwd()
fixture_dir = os.path.join(project_dir, "test", "outcomes")

# %% [markdown]
# ## Unified score schema
#
# Scores use a long-format table: each row represents a submission and one
# difficulty level. Both loaders return these columns in the same order.

# %%
schema_descriptions = [
    "Benchmark identifier.",
    "Published benchmark split or leaderboard.",
    "Submitted agent or system.",
    "Model name as published by the source.",
    "Normalized model identifier.",
    "Type of task the benchmark measures.",
    "Score metric.",
    "Difficulty level for the score.",
    "Score as a fraction from zero to one.",
    "Submission cost in US dollars, when available.",
    "Date associated with the leaderboard result.",
    "URL identifying the data source.",
    "Date the source snapshot was retrieved.",
]
schema = pd.DataFrame(
    {"column": bagutil.SCHEMA_COLUMNS, "description": schema_descriptions}
)
display(schema)

# %% [markdown]
# ## Normalize model names
#
# Normalized names are lowercase identifiers that make exact name matching
# easier across benchmarks. A later project milestone adds curated aliases.

# %%
model_names = ["Claude 3.7 Sonnet", "  "]
normalized_names = [
    bagutil.normalize_model_name(name) for name in model_names
]
display(
    pd.DataFrame(
        {"model_raw": model_names, "model": normalized_names}
    )
)

# %% [markdown]
# ## Load SWE-bench results
#
# The loader reads local JSON, converts the published resolved percentage to
# a fraction, and validates the resulting unified table.

# %%
swe_bench_file = os.path.join(
    fixture_dir,
    "Test_load_swe_bench.test1",
    "input",
    "leaderboards.json",
)
swe_bench_url = "https://example.com/leaderboards.json"
retrieved = "2026-11-20"
swe_bench_scores = bagutil.load_swe_bench(
    swe_bench_file,
    source_url=swe_bench_url,
    retrieved=retrieved,
)
display(
    swe_bench_scores[
        ["split", "agent", "model_raw", "model", "score", "cost_usd"]
    ]
)

# %% [markdown]
# ## Load GAIA results
#
# GAIA publishes a score for the full benchmark and for three levels. Its
# scores are already fractions, so the loader preserves their values.

# %%
gaia_file = os.path.join(
    fixture_dir,
    "Test_load_gaia.test1",
    "input",
    "gaia_results.json",
)
gaia_url = (
    "https://huggingface.co/datasets/gaia-benchmark/results_public"
)
gaia_scores = bagutil.load_gaia(
    gaia_file,
    source_url=gaia_url,
    retrieved=retrieved,
)
display(
    gaia_scores[
        ["split", "agent", "model_raw", "model", "difficulty", "score"]
    ]
)

# %% [markdown]
# ## Validate score data
#
# A percentage accidentally stored as a fraction violates the score range.
# Catch the expected assertion to show how validation reports invalid data.

# %%
invalid_scores = swe_bench_scores.head(1).copy()
invalid_scores.loc[invalid_scores.index[0], "score"] = 72.7
try:
    bagutil.validate_scores(invalid_scores)
except AssertionError as error:
    print(f"Expected validation error: {error}")
else:
    raise AssertionError("Expected the percent-scale score to be rejected.")

# %% [markdown]
# ## Build the committed scores table
#
# `build_scores_table` verifies each raw snapshot against its SHA-256 entry in
# `provenance.json`, loads both benchmarks, removes exact duplicates, sorts
# the rows, and validates the combined table. It reads local files only.

# %%
raw_dir = os.path.join(project_dir, "data", "raw")
scores = bagutil.build_scores_table(raw_dir)
display(pd.DataFrame({"rows": [len(scores)], "columns": [len(scores.columns)]}))
display(
    scores.groupby(["benchmark", "split"], sort=True)
    .size()
    .rename("rows")
    .reset_index()
)
display(scores.head())
