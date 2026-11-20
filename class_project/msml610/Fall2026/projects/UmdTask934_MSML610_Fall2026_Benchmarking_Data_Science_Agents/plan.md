# PR 1: Unified Leaderboard Table (SWE-bench + GAIA) Implementation Plan

> **Status: DRAFT for the team to review.** Nothing here is implemented yet. Steps use checkboxes
> (`- [ ]`) to track progress. This file is removed before the upstream PR, so the graded PR holds
> only the project itself.

**Goal:** Ship the first runnable PR of the class project: a committed, source-stamped table of
published leaderboard results for **SWE-bench** and **GAIA** in one schema, with offline loaders,
unit tests, a cleaned-up Docker skeleton, and thin notebooks that show the table.

**Architecture:** Follows the design of the sibling project UmdTask716 (Skill vs Luck), which is already merged.
- One CLI script (`fetch_leaderboards.py`) is the only code that touches the network. It saves
  slim raw snapshots plus `provenance.json` (URL, pinned revision, retrieval date, sha256) under
  `data/raw/`, then builds `data/scores.csv`.
- All parsing lives in `benchmarking_agents_utils.py` as pure functions over local files, so the
  tests and notebooks run offline.
- The table is in **long format**: one row per (submission, difficulty).

**Tech Stack:**
- Python 3.12 in the template Docker image (`python:3.12-slim`)
- `pandas` and stdlib `urllib`/`json`/`hashlib` (no `requests`, no `pyarrow`)
- `helpers` (`hdbg`, `hio`, `hparser`, `hunit_test`) and `pytest`

**Spec:** `research/ideas/draft.Benchmarking_Data_Science_Agents.md` (class repo), Milestone 1.
It's the same work as `PR_M1` ("schema and store, with two benchmarks loaded") in
`research/agentic_data_science/docs/plan.md`.

---

## Can we start now? Yes

Nothing in PR 1 waits on Dev or GP: the data is public, and the spec defines the milestone.
Checked on 2026-11-16:

| Source | Access | What it gives us |
|---|---|---|
| SWE-bench: `SWE-bench/swe-bench.github.io` `data/leaderboards.json` (pin commit `193160a4`) | Public raw GitHub file (4 MB, about 107 KB once slimmed) | 5 leaderboards (Verified 180, Lite 84, Test 24, Multimodal 22, Multilingual 13 rows) with `model_display`, `agent`, `date`, `resolved` (%), `cost` |
| GAIA: HF dataset `gaia-benchmark/results_public`, config `2023` (revision `a1f6489a` on 2026-11-20; it was `18511ffd` on 2026-11-16) | Public, not gated; JSON rows via `datasets-server.huggingface.co/rows` (no `pyarrow`), which serves only the latest revision and rate-limits (429) | validation 96 rows, test 4,226 rows (2026-11-20); about 66% have an empty `model_family`; `model`, `model_family`, `score`, `score_level1..3`, `date` |
| MLE-bench: `openai/mle-bench` README table | Public markdown table | Low/Medium/High/All medal rate, LLM, date. **PR 2** |
| DSBench, DataSciBench | Results only in SVG figures / papers | Entered by hand with citations. **PR 2** |

**Finding that shapes later PRs:** with naive name matching, only about 5 base models appear on
both SWE-bench and MLE-bench, or on both SWE-bench and GAIA. Cross-benchmark correlation
(Milestone 3) therefore needs a curated model-alias map (PR 2) and must report *n* with every
coefficient. That's planned, not a surprise.

**Blockers before Task 1 (people, not code):**
1. Yaswanth adds `rahulcs6104` and `AksshajErigisetty` as collaborators on
   `Yashu16/forked_grp8_gpsaggese.github.io`. **Rahul: done (write, 2026-11-17).** Aksshaj: not
   listed yet.
2. Team agrees on the file prefix `benchmarking_agents` and on removing Yaswanth's
   `benchmarking_agents.md` (a verbatim copy of the spec) in favor of a `README.md` that links the spec.
3. Team agrees on the split and workflow in "Who does what" below.

## Who does what

Each person owns real code with its own tests, plus one presentation piece, so the commit
history shows all three contributing.

| Person | Tasks | In short |
|---|---|---|
| **Rahul** | Task 2, Task 5, Task 7 | Schema and checks; download script, table build and `data/scores.csv`; opening the PR |
| **Yaswanth** | Task 1, Task 3, Task 6a | Skeleton and Docker; SWE-bench loader; API notebook |
| **Aksshaj** | Task 4, Task 6b | GAIA loader; `plot_best_score_over_time`, example notebook and `README.md` |

**Order** (each arrow is a real dependency):

1. **Day 1:** Yaswanth does Task 1 (renames the files everyone edits). Rahul writes Task 2 in parallel and rebases it onto Task 1 once that lands (about half a day).
2. **After Task 2 is merged:** Yaswanth (Task 3) and Aksshaj (Task 4) build their loaders in parallel. Both use only `SCHEMA_COLUMNS`, `normalize_model_name` and `validate_scores`, and their signatures are fixed below, so neither waits on the other.
3. **Meanwhile:** Rahul builds the download half of Task 5 (`_download_json`, `fetch_swe_bench`, `fetch_gaia`, the CLI). It doesn't depend on the loaders.
4. **After Tasks 3 and 4 are merged:** Rahul finishes Task 5 (`build_scores_table`, its tests, the real fetch, `data/scores.csv`).
5. **Notebooks:** Yaswanth (6a) and Aksshaj (6b) can draft early on the Task 3/4 fixtures, then finish once `data/scores.csv` exists.
6. **Last:** Rahul opens the PR (Task 7) once every task's tests pass on the team branch.

**Branching workflow** (all three people edit `benchmarking_agents_utils.py` and
`test/test_benchmarking_agents_utils.py`):

- The team branch `UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents` on `grp8` is the integration branch, and becomes the single upstream PR.
- Each task gets a short branch off the latest team branch, named `UmdTask934_<task>` (e.g. `UmdTask934_gaia_loader`).
- When the task's tests pass, open a PR **inside the team repo** (base = the team branch) and have one teammate review it before merging. That leaves a review trail per person.
- Pull the team branch before starting each task, and rebase if it moved.
- In both shared files, add your code under your own `# ####` section banner (`# Schema`, `# SWE-bench`, `# GAIA`, `# Table build`, `# Fetch`, `# Plots`), and only touch other sections in your own task's PR. That keeps merge conflicts rare.
- Needs blocker 1 first: Rahul and Aksshaj can't push branches until they're collaborators.

## Global Constraints

- Code follows `.claude/rules.md` → `coding.rules.md`:
  - `typing` hints (`List`, `Dict`, `Optional`), `os.path` not `pathlib`
  - `_LOG = logging.getLogger(__name__)`, no `print` in library code
  - `hdbg.dassert*` instead of `assert`/`raise`
  - REST docstrings with `:param`/`:return:`
  - `# ####` section banners, private helpers prefixed with `_`, Ruff line length 81
- Tests follow `testing.rules.md`:
  - `hunitest.TestCase`, classes named `Test_<function>`, methods `test1`, `test2`, …
  - Fixtures under `self.get_input_dir()`; no `/tmp`; **no network in any test**
- The CLI script follows `script.rules.md` (`_parse()` / `_main(parser)`, `hparser.add_verbosity_arg`).
- Notebooks are thin (all logic in `benchmarking_agents_utils.py`), paired with jupytext percent `.py` files.
- **Every row of `data/scores.csv` has a non-empty `source_url` and `retrieved` date.**
  Scores are fractions in `[0, 1]`. Dates are ISO `YYYY-MM-DD`.
- Files only under `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/`.
  Stage only that folder; never `git add -A`.
- Commit messages are `UmdTask934: <Imperative description>`, with no co-author trailers. Each
  task's owner commits and pushes their own branch to remote `grp8`.
- `requirements.txt` changes are pinned (`pkg==x.y.z`), matching UmdTask716's practice.

Paths below are relative to the project folder, `$P` =
`/git_root/class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents`
inside the container. Test command:
`./docker_cmd.sh "cd $P && python -m pytest test/test_benchmarking_agents_utils.py"` (pass the
file explicitly; `class_project/msml610/conftest.py` blocks directory collection).

## Review Focus

1. **Percent vs. fraction:** SWE-bench `resolved` is a percent (`72.7`) and GAIA `score` is a
   fraction (`0.376`). Both must land as fractions, or every later comparison is off by 100×.
   Pinned by Task 3 `test2` and Task 4 `test2`.
2. **Upstream field renames:** if a leaderboard file drops or renames a field, loading must fail
   loudly, naming the field, instead of filling the column with NaN. Pinned by Task 3 `test3`.
3. **Empty model names:** GAIA `model_family` is sometimes `""`. Keep the row with
   `model_raw = ""` and `model = "unknown"`, never drop it silently. Pinned by Task 4 `test3`.
4. **Duplicate submissions:** GAIA has repeated identical rows. Exact duplicates go; distinct
   submissions of the same model stay. Pinned by Task 5 `test2`.
5. **Snapshot integrity:** a raw file edited by hand after fetching must be detectable. Pinned by
   Task 5 `test3` (the sha256 in `provenance.json` doesn't match → `build_scores_table` fails).

---

## File Structure

| File | Responsibility |
|---|---|
| `benchmarking_agents_utils.py` | Schema, validation, the per-benchmark loaders, table build, plus download helpers used only by the script |
| `fetch_leaderboards.py` | CLI: download the raw snapshots, write `provenance.json`, build `data/scores.csv` (the only networked code) |
| `data/raw/swe_bench_leaderboards.json` | Slim SWE-bench snapshot (fields listed in Task 3) |
| `data/raw/gaia_results.json` | GAIA rows for both splits, with `system_prompt` dropped |
| `data/raw/provenance.json` | Per raw file: `url`, `revision`, `retrieved`, `sha256` |
| `data/scores.csv` | The unified table (the PR 1 artifact) |
| `test/test_benchmarking_agents_utils.py` | Unit tests, offline |
| `test/outcomes/<Class.method>/input/*.json` | Small hand-written fixtures |
| `benchmarking_agents.API.ipynb` / `.py` | Schema and loaders walkthrough on the fixtures |
| `benchmarking_agents.example.ipynb` / `.py` | First look at `data/scores.csv` |
| `README.md` | Quick start, data provenance, how to refresh the data, link to the spec and #934 |

The owner of each file section is listed in "Who does what" above.
| Renamed or removed template files | See Task 1 |

---

### Task 1: Clean up the skeleton and get Docker running (owner: Yaswanth)

**Files:**
- Rename: `template_utils.py` → `benchmarking_agents_utils.py`
- Rename: `template.API.{ipynb,py}` → `benchmarking_agents.API.{ipynb,py}`
- Rename: `template.example.{ipynb,py}` → `benchmarking_agents.example.{ipynb,py}`
- Modify: `docker_name.sh` (set `IMAGE_NAME=umd_msml610_benchmarking_data_science_agents`)
- Modify: `test/test_docker_template.py` (notebook names `benchmarking_agents.example.ipynb` and `benchmarking_agents.API.ipynb`; docstring mentions this project, not `project_template`)
- Modify: `requirements.txt` (add `pytest==9.1.1`, the version UmdTask716 uses)
- Delete: `utils.sh` (unused: the `docker_*.sh` scripts source `$GIT_ROOT/class_project/project_template/utils.sh`)
- Delete: `benchmarking_agents.md` (per blocker 2; Task 6b adds `README.md`)
- Regenerate: `docker_build.version.log` (by the build)

**Interfaces:**
- Produces: a built image `gpsaggese/umd_msml610_benchmarking_data_science_agents` that runs `pytest`

- [ ] **Step 1:** `git mv` the five template files above; edit `docker_name.sh`, `test/test_docker_template.py` and `requirements.txt`.
- [ ] **Step 2:** Build the image. Run `export DOCKER_ENGINE=docker` first on Docker Desktop (the default is Apple `container`, whose build log in the template shows `Operation not supported by device`).
  Run: `./docker_build.sh`. Expected: it ends without error and `docker_build.version.log` lists `pytest 9.1.1`.
- [ ] **Step 3:** Run: `./docker_cmd.sh "python -c 'import helpers.hdbg, pandas, pytest; print(\"ok\")'"`. Expected: `ok`.
- [ ] **Step 4:** Commit: `git add <project folder>` then `git commit -m "UmdTask934: Rename template files and set the Docker image name"`.

### Task 2: Schema and validation (owner: Rahul)

**Files:**
- Modify: `benchmarking_agents_utils.py` (replace the template body; module docstring with `Import as: import benchmarking_agents_utils as bagutil`)
- Create: `test/test_benchmarking_agents_utils.py`

**Interfaces:**
- Produces:
  - `SCHEMA_COLUMNS: List[str]` =
    `["benchmark", "split", "agent", "model_raw", "model", "task_type", "metric", "difficulty", "score", "cost_usd", "date", "source_url", "retrieved"]`
  - `validate_scores(df: pd.DataFrame) -> None`: `hdbg.dassert`s that
    - the columns equal `SCHEMA_COLUMNS` in order
    - `score` is in `[0, 1]` with no NaN
    - `date` and `retrieved` parse as `%Y-%m-%d`
    - `source_url` is non-empty
    - `benchmark` is in `{"swe_bench", "gaia"}` (PR 2 extends this set)
  - `normalize_model_name(name: str) -> str`: lowercase, runs of non-`[a-z0-9.]` become `-`, strip `-`; `""` gives `"unknown"`. (PR 2 adds the alias map on top.)

- [ ] **Step 1: Write the failing tests**

```python
class Test_normalize_model_name(hunitest.TestCase):
    def test1(self) -> None:
        self.assert_equal(bagutil.normalize_model_name("Claude 3.7 Sonnet"), "claude-3.7-sonnet")
    def test2(self) -> None:
        self.assert_equal(bagutil.normalize_model_name("  "), "unknown")

class Test_validate_scores(hunitest.TestCase):
    def test1(self) -> None:
        # One valid row (built inline with all SCHEMA_COLUMNS) passes.
        bagutil.validate_scores(_make_row(score=0.5))
    def test2(self) -> None:
        # A percent-scale score is rejected.
        with self.assertRaises(AssertionError):
            bagutil.validate_scores(_make_row(score=72.7))
    def test3(self) -> None:
        # An empty source_url is rejected.
        with self.assertRaises(AssertionError):
            bagutil.validate_scores(_make_row(source_url=""))
```
(`_make_row(**overrides) -> pd.DataFrame` is a module-level test helper returning a one-row frame with valid defaults.)

- [ ] **Step 2:** Run the test command. Expected: FAIL (`AttributeError: ... has no attribute 'normalize_model_name'`).
- [ ] **Step 3:** Implement `SCHEMA_COLUMNS`, `validate_scores`, `normalize_model_name`.
- [ ] **Step 4:** Run the test command. Expected: 5 passed.
- [ ] **Step 5:** Commit: `UmdTask934: Add the unified score schema and validation`.

### Task 3: SWE-bench loader (owner: Yaswanth)

**Files:**
- Modify: `benchmarking_agents_utils.py`
- Modify: `test/test_benchmarking_agents_utils.py`
- Create: `test/outcomes/Test_load_swe_bench.test1/input/leaderboards.json` (and the same for `test2`, `test3`): 2 leaderboards, 3 results total, in the slim format

**Interfaces:**
- Consumes: `SCHEMA_COLUMNS`, `normalize_model_name`
- Produces: `load_swe_bench(file_name: str, *, source_url: str, retrieved: str) -> pd.DataFrame`
  - Input: slim JSON `{"leaderboards": [{"name": str, "results": [ {...} ]}]}`, each result
    with `name, model_display, agent, agent_org, model_org, date, resolved, cost, instance_cost,
    os_model, os_system, checked, folder` (the field set the Task 5 fetcher keeps)
  - One output row per result:
    - `benchmark="swe_bench"`, `split=<leaderboard name lowercased>` (`verified`, `lite`, …)
    - `agent=agent`, `model_raw=model_display` (falls back to `name` if empty), `model=normalize_model_name(model_raw)`
    - `task_type="coding"`, `metric="resolved_rate"`, `difficulty="all"`
    - `score=resolved / 100`, `cost_usd=cost` (NaN if missing), `date=date`
  - `hdbg.dassert`s that `resolved`, `date` and `agent` exist in every result, naming the missing key

- [ ] **Step 1: Write the failing tests**

```python
class Test_load_swe_bench(hunitest.TestCase):
    def test1(self) -> None:
        # Fixture: 2 leaderboards, 3 results -> 3 rows, schema columns, splits {"verified", "lite"}.
        df = bagutil.load_swe_bench(file_name, source_url="u", retrieved="2026-11-16")
        self.assertEqual(list(df.columns), bagutil.SCHEMA_COLUMNS)
        self.assertEqual(len(df), 3)
        self.assertEqual(set(df["split"]), {"verified", "lite"})
    def test2(self) -> None:
        # resolved=72.7 in the fixture -> score 0.727.
        self.assertAlmostEqual(df.loc[df["agent"] == "mini-SWE-agent", "score"].iloc[0], 0.727)
    def test3(self) -> None:
        # A fixture result missing "resolved" -> AssertionError whose message contains "resolved".
        with self.assertRaises(AssertionError) as cm:
            bagutil.load_swe_bench(file_name, source_url="u", retrieved="2026-11-16")
        self.assertIn("resolved", str(cm.exception))
```

- [ ] **Step 2:** Run the test command. Expected: FAIL (no `load_swe_bench`).
- [ ] **Step 3:** Implement `load_swe_bench` with `hio.from_json`, then `validate_scores` on the result before returning it.
- [ ] **Step 4:** Run the test command. Expected: all pass.
- [ ] **Step 5:** Commit: `UmdTask934: Add the SWE-bench leaderboard loader`.

### Task 4: GAIA loader (owner: Aksshaj)

**Files:**
- Modify: `benchmarking_agents_utils.py`, `test/test_benchmarking_agents_utils.py`
- Create: `test/outcomes/Test_load_gaia.test{1,2,3}/input/gaia_results.json`: a JSON list of rows

**Interfaces:**
- Consumes: `SCHEMA_COLUMNS`, `normalize_model_name`
- Produces: `load_gaia(file_name: str, *, source_url: str, retrieved: str) -> pd.DataFrame`
  - Input: list of `{"split": "validation"|"test", "model", "model_family", "url", "organisation", "score", "score_level1", "score_level2", "score_level3", "date"}`
  - **Four** output rows per input row, for `difficulty` in `all, level1, level2, level3`
    (from `score`, `score_level1`, …):
    - `benchmark="gaia"`, `split=split`, `agent=model` (the GAIA "model" is the submitted system)
    - `model_raw=model_family`, `model=normalize_model_name(model_family)`
    - `task_type="reasoning"`, `metric="accuracy"`, `cost_usd=NaN`
  - A row whose level score is null yields no row for that level. That's logged at `_LOG.debug`, and the count is logged at `info`.

- [ ] **Step 1: Write the failing tests**

```python
class Test_load_gaia(hunitest.TestCase):
    def test1(self) -> None:
        # 2 input rows -> 8 output rows; difficulties {"all", "level1", "level2", "level3"}.
        ...
    def test2(self) -> None:
        # Input score 0.37575757 -> row (difficulty="all") score 0.37575757 (already a fraction, unchanged).
        ...
    def test3(self) -> None:
        # Input model_family="" -> rows kept, model_raw == "", model == "unknown".
        ...
```

- [ ] **Step 2:** Run the test command. Expected: FAIL (no `load_gaia`).
- [ ] **Step 3:** Implement `load_gaia` (a `pd.melt` over the four score columns is the natural fit), then `validate_scores`.
- [ ] **Step 4:** Run the test command. Expected: all pass.
- [ ] **Step 5:** Commit: `UmdTask934: Add the GAIA leaderboard loader`.

### Task 5: Table build, provenance and the fetch script (owner: Rahul)

The download half (`_download_json`, the two fetchers, the CLI) can start right after Task 2.
`build_scores_table` and its tests wait for Tasks 3 and 4.

**Files:**
- Modify: `benchmarking_agents_utils.py`, `test/test_benchmarking_agents_utils.py`
- Create: `fetch_leaderboards.py` (executable, `#!/usr/bin/env python`)
- Create: `test/outcomes/Test_build_scores_table.test{1,2,3}/input/` (a mini `raw/` dir: both slim files plus `provenance.json`)
- Create (by running the script): `data/raw/swe_bench_leaderboards.json`, `data/raw/gaia_results.json`, `data/raw/provenance.json`, `data/scores.csv`

**Interfaces:**
- Consumes: `load_swe_bench`, `load_gaia`, `validate_scores`
- Produces:
  - `SWE_BENCH_SITE_SHA = "193160a463a435d05cf44a1fa9dc5eac832113c3"`, `GAIA_REVISION = "a1f6489aea6808003b35465341a3cbcb84f15c82"` (the expected revision; the GAIA dataset moves, so the saved snapshot plus its sha256 is what pins the data; the script's `--swe_bench_sha` and `--gaia_revision` flags override them)
  - `build_scores_table(raw_dir: str) -> pd.DataFrame`:
    - Reads `provenance.json` (`{file_name: {"url", "revision", "retrieved", "sha256"}}`) and `hdbg.dassert`s that each file's sha256 matches.
    - Calls the two loaders with each file's `url` and `retrieved`, concatenates the results, drops exact duplicates (logging how many), sorts by `benchmark, split, date, agent`, and calls `validate_scores`.
  - `fetch_swe_bench(dst_dir: str, *, sha: str) -> Dict[str, str]`: downloads
    `https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/<sha>/data/leaderboards.json`,
    keeps only the Task 3 field set, writes `swe_bench_leaderboards.json`, and returns its provenance entry.
  - `fetch_gaia(dst_dir: str, *, revision: str) -> Dict[str, str]`: pages
    `https://datasets-server.huggingface.co/rows?dataset=gaia-benchmark/results_public&config=2023&split=<split>&offset=<k>&length=100`
    for `validation` and `test`, drops `system_prompt`, adds `split`, writes
    `gaia_results.json`, and returns its provenance entry. It warns if the HF API's current `sha`
    differs from `revision`, because datasets-server serves only the latest version.
  - `_download_json(url: str) -> Any` (stdlib `urllib.request` with a 60 s timeout).
  - CLI: `fetch_leaderboards.py --dst_dir data [--swe_bench_sha ...] [--gaia_revision ...]` writes `data/raw/*` plus `data/scores.csv`.

- [ ] **Step 1: Write the failing tests** (offline; the fetchers aren't unit-tested because they only do I/O)

```python
class Test_build_scores_table(hunitest.TestCase):
    def test1(self) -> None:
        # Mini raw dir (3 SWE results + 2 GAIA rows) -> 3 + 8 = 11 rows; benchmarks {"swe_bench", "gaia"};
        # every source_url equals the url in provenance.json for its file.
        ...
    def test2(self) -> None:
        # GAIA fixture contains one exact duplicate row -> still 11 rows, not 15.
        ...
    def test3(self) -> None:
        # provenance.json sha256 for gaia_results.json is wrong -> AssertionError mentioning "sha256".
        ...
```

- [ ] **Step 2:** Run the test command. Expected: FAIL (no `build_scores_table`).
- [ ] **Step 3:** Implement `build_scores_table`, the two fetchers, `_download_json` and `fetch_leaderboards.py` (`_parse`/`_main`; `hdbg.init_logger`; writes the CSV with `index=False`).
- [ ] **Step 4:** Run the test command. Expected: all pass.
- [ ] **Step 5:** Fetch the real data (needs internet). Run: `./docker_cmd.sh "cd $P && ./fetch_leaderboards.py --dst_dir data"`.
  Expected: the log reports about 323 SWE-bench rows and about 4 × 4,301 GAIA rows before dedup (fewer after null levels and duplicates); `data/raw/` stays under ~2 MB.
- [ ] **Step 6:** Commit the code, tests and data: `UmdTask934: Add the leaderboard fetch script and the unified scores table`.

### Task 6a: API notebook (owner: Yaswanth)

**Files:**
- Modify: `benchmarking_agents.API.ipynb` / `.py`: title `# Benchmark Leaderboards API Overview`. Sections: the schema (`SCHEMA_COLUMNS` table), `normalize_model_name`, `load_swe_bench` and `load_gaia` on the Task 3/4 fixtures, `validate_scores` catching a percent-scale score, `build_scores_table`.

**Interfaces:**
- Consumes: everything from Tasks 2–5 (the `build_scores_table` section waits for Task 5; the rest can be drafted after Tasks 3 and 4)

- [ ] **Step 1:** Write the notebook in the paired `.py` file and sync it with `jupytext --sync`.
- [ ] **Step 2:** Run it top to bottom in the container. Run: `./docker_cmd.sh "cd $P && python benchmarking_agents.API.py"`. Expected: exit 0.
- [ ] **Step 3:** Commit: `UmdTask934: Add the API notebook`.

### Task 6b: Plot helper, example notebook and README (owner: Aksshaj)

**Files:**
- Modify: `benchmarking_agents_utils.py`: add `plot_best_score_over_time(df: pd.DataFrame, *, benchmark: str, split: str) -> matplotlib.axes.Axes` (cumulative max of `score` by `date`) so the notebook stays thin.
- Modify: `test/test_benchmarking_agents_utils.py`
- Modify: `benchmarking_agents.example.ipynb` / `.py`: load `data/scores.csv` and show:
  - row counts per `benchmark × split`
  - the top 10 of SWE-bench Verified by `score`
  - GAIA test mean score by `difficulty`
  - best SWE-bench Verified score over time (one line plot)
  - a markdown cell ending with "next: MLE-bench, DSBench, model aliases (PR 2)"
- Create: `README.md` (per `readme_dir.rules.md`): what the project is (plain language first), team, #934, link to the spec, quick start (build, Jupyter, run the notebooks), data provenance table, "Refresh the data" (the fetch command), "Run the unit tests" (the explicit-file command)
- Test: `test/test_docker_template.py` runs both notebooks in Docker (`@pytest.mark.slow`, inherited from the template)

**Interfaces:**
- Consumes: `SCHEMA_COLUMNS` (Task 2); `data/scores.csv` (Task 5)
- Produces: `plot_best_score_over_time` (above)

- [ ] **Step 1:** Add `Test_plot_best_score_over_time.test1`: on a 3-row frame with dates `2024-01-01`, `2024-06-01` and `2025-01-01` and scores `0.2`, `0.1`, `0.5`, the plotted y-values are `[0.2, 0.2, 0.5]`. Run it; expect FAIL.
- [ ] **Step 2:** Implement `plot_best_score_over_time`; run the tests; expect all pass. (Steps 1–2 only need Task 2, so they can be done early.)
- [ ] **Step 3:** Write the example notebook in the paired `.py` file and sync it with `jupytext --sync`.
- [ ] **Step 4:** Run it top to bottom in the container. Run: `./docker_cmd.sh "cd $P && python benchmarking_agents.example.py"`. Expected: exit 0.
- [ ] **Step 5:** Once Task 6a is merged too, run the Docker notebook tests: `python -m pytest test/test_docker_template.py` on the host (it drives Docker). Expected: 2 passed.
- [ ] **Step 6:** Write `README.md`.
- [ ] **Step 7:** Commit: `UmdTask934: Add the example notebook, the score-over-time plot and the README`.

### Task 7: Open the PR (owner: Rahul)

- [ ] **Step 1:** Push the branch to `grp8` (with Rahul's approval).
- [ ] **Step 2:** Open the PR from `Yashu16:UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents` into `gpsaggese/gpsaggese.github.io:master`:
  - title = the branch name
  - body per `.claude/templates/github_PR_description.template.md`, with "Related to #934" (not "closes") and a mention that it covers `PR_M1` of `research/agentic_data_science/docs/plan.md`
  - reviewers: the TAs and `@gpsaggese`; assign the team
  - delete `plan.md` from the project folder first
- [ ] **Step 3:** Post the direct PR link on #934 and in Slack (GP asks for links).

---

## After PR 1 (outline only; each gets its own plan once PR 1 is merged)

- **PR 2 (≈ `PR_M2`, Milestones 1–2):**
  - MLE-bench loader (README table at a pinned commit; `difficulty` low/medium/high/all; `task_type="ml_engineering"`)
  - Hand-entered `data/manual/dsbench.csv` and `datascibench.csv`, with a paper/table reference per row
  - `data/model_aliases.csv` (raw → canonical; ensembles and `undisclosed` map to `unknown`)
  - A taxonomy table seeded from `sota_eda.md` and `deep-research-report.md`
- **PR 3 (≈ `PR_M3`, Milestones 3–5):**
  - Spearman rank correlation between benchmark pairs over shared canonical models, with *n* and a bootstrap CI (needs `scipy`)
  - Heatmap, capability-gap scatter and radar plots
  - GAIA level stability and MLE-bench low/medium/high stability
- **PR 4 (≈ `PR_M4`, Milestone 6):** reproducibility audit on 10–20 GAIA level-1 validation questions with a free-tier model. GAIA questions are `gated: auto`, so each runner needs an HF token that has accepted the terms.
- **Complexity item (pick one):** benchmark saturation over time (the GAIA and SWE-bench dates are already in PR 1's table), or score per dollar (SWE-bench `cost` is already in PR 1's table).
