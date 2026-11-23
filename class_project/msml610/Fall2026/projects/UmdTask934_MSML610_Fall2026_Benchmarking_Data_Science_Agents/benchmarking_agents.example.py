# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Published benchmark results: a first look
#
# - Explore the committed SWE-bench and GAIA leaderboard results offline
# - The walkthrough:
#   - Check the table and its sources
#   - Inspect submission counts and scores within each benchmark
#   - Follow the best SWE-bench Verified score over submission dates
# - Scores are fractions between 0 and 1
#   - SWE-bench measures resolved coding tasks
#   - GAIA measures accuracy on reasoning questions
#   - The two metrics describe different tasks and are not interchangeable

# %%
# %load_ext autoreload
# %autoreload 2

import logging

import matplotlib.pyplot as plt
import pandas as pd

# %%
import helpers.hnotebook as hnotebook

import benchmarking_agents_utils as utils

# Initialize notebook configuration and logging.
hnotebook.config_notebook()
_LOG = logging.getLogger(__name__)
utils.init_loggers(_LOG)

# Convert `display` into `print()` when running outside IPython.
try:
    from IPython.display import display
except ImportError:
    display = print  # type: ignore

# %% [markdown]
# # Part 1: Explore the saved leaderboard table
#
# ## Cell 1.1: Load the table and check its provenance
#
# - Run from the project directory so the relative data path resolves
# - Gzip compression is detected automatically by `pandas`
# - Preserve empty published model names when reading the CSV
# - Each row describes one submission at one difficulty
#   - The same GAIA submission can contribute up to four rows
#   - `date` is the submission date; `retrieved` is the download date

# %%
# Read the saved table; no download or API credentials are needed.
scores = pd.read_csv(
    "data/scores.csv.gz",
    keep_default_na=False,
    na_values={"cost_usd": [""]},
)
utils.validate_scores(scores)
print("table_shape=", scores.shape)
display(scores.head())

# %%
# Show the source URLs and retrieval dates stored on the actual table rows.
provenance = scores[["benchmark", "source_url", "retrieved"]]
display(provenance.drop_duplicates().reset_index(drop=True))

# %% [markdown]
# ## Cell 1.2: Count rows by benchmark and split
#
# - Count long-format rows separately from overall submission rows
# - GAIA difficulty rows explain why its row count exceeds its submissions
# - Counts reflect the saved snapshot after exact duplicate removal

# %%
# Count every score row in the long-format table.
row_counts = scores.groupby(["benchmark", "split"]).size()
display(row_counts.rename("score_rows").to_frame())

# %%
# Count overall-score submissions without also counting their difficulty rows.
overall = scores.loc[scores["difficulty"] == "all"]
submission_counts = overall.groupby(["benchmark", "split"]).size()
display(submission_counts.rename("overall_submissions").to_frame())

# %% [markdown]
# ## Cell 1.3: Inspect the top 10 SWE-bench Verified submissions
#
# - Rank submissions by their fraction of resolved tasks
# - Show both the agent and the published base model
# - A model can appear more than once under different submitted systems
# - A missing cost means that the leaderboard did not report it

# %%
# Select a single benchmark and split before ranking its submissions.
verified = overall.loc[
    (overall["benchmark"] == "swe_bench")
    & (overall["split"] == "verified")
]
top_verified = verified.nlargest(10, "score")
display(top_verified[["agent", "model_raw", "score", "cost_usd", "date"]])

# %% [markdown]
# ## Cell 1.4: Compare GAIA test scores across difficulties
#
# - Compute the mean published submission score for each difficulty
# - Include the number of contributing submissions beside each mean
# - Missing level scores were skipped by the loader
#   - Difficulty groups can therefore have different sample sizes
# - These are submission averages, not a question-weighted benchmark score
# - An unknown model family still represents a valid published submission

# %%
# Summarize test submissions separately for each GAIA difficulty.
gaia_test = scores.loc[
    (scores["benchmark"] == "gaia") & (scores["split"] == "test")
]
gaia_summary = gaia_test.groupby("difficulty").agg(
    mean_score=("score", "mean"),
    n_submissions=("score", "size"),
)
display(gaia_summary.reindex(["all", "level1", "level2", "level3"]))

# %% [markdown]
# ## Cell 1.5: Follow the best SWE-bench Verified score over time
#
# **Goal**
#
# - See how the best recorded overall score changes by submission date
#
# **Description**
#
# - Input: the saved table filtered to SWE-bench Verified overall scores
# - Panel: cumulative best score, on a fixed 0 to 1 scale
# - The line stays flat when a later submission has a lower score

# %%
# Draw the curve using the tested utility rather than inline plotting logic.
ax = utils.plot_best_score_over_time(
    scores, benchmark="swe_bench", split="verified"
)
plt.show()

# %% [markdown]
# **Interpretation**
#
# - Read upward steps as improvements among the recorded submissions
# - Flat sections mean no improvement among those submissions
#   - They do not establish that research progress stopped
# - The history is reconstructed from dates in one saved leaderboard snapshot
#   - It is not a collection of daily historical leaderboard snapshots
#
# **Implementation** `plot_best_score_over_time()`
#
# - Selects the requested benchmark and split at overall difficulty
# - Takes the maximum score on each submission date
# - Sorts dates and plots their cumulative maximum

# %% [markdown]
# ## Next steps
#
# - Keep comparisons within each benchmark until model aliases are curated
# - Use the API notebook for the schema and loader walkthrough
# - next: MLE-bench, DSBench, model aliases (PR 2)
