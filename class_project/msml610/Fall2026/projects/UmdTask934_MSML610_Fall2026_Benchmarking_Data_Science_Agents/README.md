# Benchmarking Data Science Agents

- **Goal**: Put published agent benchmark results into one table that can be
  inspected and reproduced offline
- **Input**: Public SWE-bench and GAIA leaderboard snapshots
- **Output**:
  - A unified table in `data/scores.csv.gz`
  - Raw snapshots and their provenance in `data/raw/`
  - Notebooks showing the schema and example analysis
- **Users**: Students and researchers comparing submitted systems within a benchmark

## Team and Project Scope

| Team Member | Contributions |
| :---------- | :------------ |
| Yaswanth (`Yashu16`) | Docker setup, SWE-bench loader, API notebook |
| Aksshaj (`AksshajErigisetty`) | GAIA loader, time plot, example notebook, README |
| Rahul (`rahulcs6104`) | Schema, validation, downloads, unified table, upstream PR |

- Course project: [issue #934][issue]
- Specification: [Benchmarking Data Science Agents][spec]
- This first milestone collects published results; it does not run agent benchmarks
- SWE-bench resolved rate and GAIA accuracy measure different tasks
  - Compare submissions within the same benchmark and split
  - Cross-benchmark model aliases and correlation analysis belong to later PRs

## Quick Start

- Start Docker Desktop
- From an existing repository checkout, initialize the shared helpers dependency:

  ```bash
  > git -c submodule.helpers_root.url=https://github.com/gpsaggese/helpers.git \
      submodule update --init helpers_root
  > PROJECT_PATH=class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents
  > cd "$PROJECT_PATH"
  > export DOCKER_ENGINE=docker
  > ./docker_build.sh
  ```

- Run the Docker wrappers from a repository path without spaces
  - The shared wrapper currently uses unquoted filesystem paths
  - The direct Docker commands below support paths containing spaces
- Launch JupyterLab and open the URL printed by the command:

  ```bash
  > ./docker_jupyter.sh
  ```

- Run notebook cells from top to bottom, with the project directory as the kernel's
  working directory:
  - `benchmarking_agents.example.ipynb`: inspect the committed results and time plot
  - `benchmarking_agents.API.ipynb`: schema and loader walkthrough, owned by Task 6a
- Read the compressed table directly in Python:

  ```python
  import pandas as pd

  scores = pd.read_csv(
      "data/scores.csv.gz",
      keep_default_na=False,
      na_values={"cost_usd": [""]},
  )
  ```

- The explicit CSV options preserve empty published names and missing numeric costs
- The committed data needs no download or API credentials

## Data Provenance

- The committed snapshot was retrieved on 2026-11-23
- It contains 17,594 score rows after exact duplicate removal
- Every row records a `source_url` and `retrieved` date

| Benchmark | Published Source | Recorded Revision | Score Rows | Retrieved |
| :-------- | :--------------- | :---------------- | :--------- | :-------- |
| SWE-bench | [Leaderboard JSON][swe-source] | `193160a463a435d05cf44a1fa9dc5eac832113c3` | 323 | 2026-11-23 |
| GAIA | [Public results dataset][gaia-source] | `4b950a33b8d76784ea3dc2e660c7823a0fde03c0` | 17,271 | 2026-11-23 |

- `data/raw/provenance.json` records the source, revision, retrieval date, and SHA256
  of each saved snapshot
- `build_scores_table()` checks snapshot hashes before parsing
- SWE-bench percentages are converted to fractions; GAIA scores are already fractions
- One row represents a submission at one difficulty
  - SWE-bench uses `all`
  - GAIA uses `all`, `level1`, `level2`, and `level3`
  - Null difficulty scores are skipped and logged; zero scores are retained
- Empty GAIA model families remain `model_raw=""` with `model="unknown"`
- Exact duplicate rows are removed; distinct submissions by the same model remain
- `date` describes a submission; `retrieved` describes the saved snapshot
- GAIA means in the example are submission averages, not question-weighted scores
- The time plot reconstructs a cumulative best from dates in one saved snapshot
  - It uses overall scores, a maximum per date, and a cumulative maximum
  - It does not represent an archive of historical daily leaderboards

## Structure of the Dir

| Directory | Description |
| :-------- | :---------- |
| `data/` | Compressed unified table |
| `data/raw/` | Saved snapshots and hash-stamped provenance |
| `test/` | Utility tests, notebook integration tests, and small fixtures |

## Description of Files

- Python and Markdown files, alphabetical by path:

| File | Description | Cluster |
| :--- | :---------- | :------ |
| `README.md` | Setup, provenance, refresh, and review instructions | Documentation |
| `benchmarking_agents.API.py` | Paired API notebook source | Notebooks |
| `benchmarking_agents.example.py` | Paired example analysis source | Notebooks |
| `benchmarking_agents_utils.py` | Schema, loaders, table builder, downloads, and plot helper | Shared Utilities |
| `docker_scripts.README.md` | Shared Docker wrapper reference | Infrastructure |
| `fetch_leaderboards.py` | Download snapshots or rebuild the table offline | Data Collection |
| `plan.md` | Team implementation plan, removed before the upstream PR | Planning |
| `test/__init__.py` | Test package marker | Tests |
| `test/test_benchmarking_agents_utils.py` | Offline utility tests | Tests |
| `test/test_docker_template.py` | Docker notebook integration tests | Tests |

## Description of Executables

- `fetch_leaderboards.py` collects data or rebuilds the saved table
- Shell scripts manage the project image and container sessions
- Detailed wrapper flags are described in [docker_scripts.README.md](docker_scripts.README.md)

| Command | Purpose |
| :------ | :------ |
| `./docker_build.sh` | Build the project image |
| `./docker_jupyter.sh` | Start JupyterLab in the image |
| `./docker_cmd.sh "<command>"` | Execute a command in a temporary container |
| `./docker_bash.sh` | Start an interactive container shell |
| `./docker_exec.sh` | Enter a running project container |
| `./docker_clean.sh` | Remove project Docker images and containers |
| `./docker_push.sh` | Publish the project image when explicitly needed |
| `./run_jupyter.sh` | Jupyter entry point used inside the container |
| `./version.sh` | Report image package versions during the build |
| `./fetch_leaderboards.py --help` | Show the data collection CLI |

### Output Dir

- The fetch script writes to `--dst_dir`, which defaults to `data`
- `--overwrite` permits replacing the destination's generated files
- The class repository's 500 KB per-file limit motivates gzip for the large files

```text
data/
    scores.csv.gz
    raw/
        swe_bench_leaderboards.json
        gaia_results.json.gz
        provenance.json
```

## Refresh the Data

- Set the container project path from the project directory:

  ```bash
  > P=/git_root/class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents
  ```

- Rebuild the unified table from the saved snapshots, without network access:

  ```bash
  > ./docker_cmd.sh "cd $P && ./fetch_leaderboards.py --dst_dir data --overwrite --no_download"
  ```

- Download current results and rebuild the table; this replaces the saved data:

  ```bash
  > ./docker_cmd.sh "cd $P && ./fetch_leaderboards.py --dst_dir data --overwrite"
  ```

- Override source revisions when intentionally updating the snapshot:

  ```bash
  > ./docker_cmd.sh "cd $P && ./fetch_leaderboards.py --dst_dir data --overwrite --swe_bench_sha <commit> --gaia_revision <revision>"
  ```

- The Hugging Face rows service serves the latest dataset revision
  - The fetcher warns if it differs from the requested revision
  - Provenance records the actual revision and verifies it stayed stable during fetch
- Review changed data and provenance together before committing a refresh

## Run the Unit Tests

- Pass the test file explicitly; the course-level collection hook blocks directory
  collection:

  ```bash
  > ./docker_cmd.sh "cd $P && python -m pytest test/test_benchmarking_agents_utils.py"
  ```

- Run the paired example script:

  ```bash
  > ./docker_cmd.sh "cd $P && python benchmarking_agents.example.py"
  ```

- Sync notebook edits made in the percent-format Python file:

  ```bash
  > ./docker_cmd.sh "cd $P && jupytext --sync benchmarking_agents.example.py"
  ```

- After both notebook contributions are merged, run their integration tests from
  the project directory on the host, with the helpers test environment configured:

  ```bash
  > python -m pytest test/test_docker_template.py
  ```

### Direct Docker Commands for Paths Containing Spaces

- These commands use the same Dockerfile and image as the wrappers:

  ```bash
  > docker build -t gpsaggese/umd_msml610_benchmarking_data_science_agents .
  > ROOT=$(git rev-parse --show-toplevel)
  > P=/git_root/class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents
  > docker run --rm --network none \
      -v "$ROOT:/git_root" \
      -e PYTHONPATH=/git_root:/git_root/helpers_root \
      -e CSFY_GIT_ROOT_PATH=/git_root \
      -e CSFY_HOST_OS_NAME="$(uname -s)" \
      -e MPLBACKEND=Agg \
      -w "$P" \
      gpsaggese/umd_msml610_benchmarking_data_science_agents \
      python -m pytest test/test_benchmarking_agents_utils.py
  ```

- Replace the final command with `python benchmarking_agents.example.py` to check
  the paired script in the same offline container

## Description of Architecture

- `fetch_leaderboards.py` is the network entry point
- `benchmarking_agents_utils.py` contains parsing and validation over local files
  - The CLI calls its download helpers only when downloading is requested
  - Tests and notebooks use local data
- Notebooks call the shared utility module for reusable plotting logic
- Notebook `.py` and `.ipynb` files are kept paired with Jupytext

[issue]: https://github.com/gpsaggese/gpsaggese.github.io/issues/934
[spec]: https://github.com/gpsaggese/gpsaggese.github.io/blob/master/research/ideas/draft.Benchmarking_Data_Science_Agents.md
[swe-source]: https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/193160a463a435d05cf44a1fa9dc5eac832113c3/data/leaderboards.json
[gaia-source]: https://huggingface.co/datasets/gaia-benchmark/results_public/tree/4b950a33b8d76784ea3dc2e660c7823a0fde03c0/2023

# Review roadmap

- Use this map to review the data pipeline and the example analysis
- **Purpose**: Inspect published benchmark submissions reproducibly offline
- Entry points, in run order:
  - `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/fetch_leaderboards.py`: optional snapshot refresh or offline rebuild
  - `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents.API.py`: schema and loader walkthrough
  - `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents.example.py`: saved-table analysis and the cumulative best plot
- Layers, bottom first:
  - `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents_utils.py`: schema, loaders, table build, fetch, plots
  - `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/fetch_leaderboards.py`: CLI orchestration
- **Cycles in the local Python import graph**: none

## Testing

- From the project directory with the helpers environment configured:

  ```bash
  > python -m pytest test/test_benchmarking_agents_utils.py
  > ./docker_cmd.sh "cd $P && python -m pytest test/test_benchmarking_agents_utils.py"
  ```

## Files and Reading Time

- Reading speeds, in lines per minute: skim 100; code 20; docs/data 30; tests 40
- Total estimated reading time: 194 minutes, about 3 hours
- Rows are ordered by code, doc, test, and data
  - Code starts with shared support, followed by entry points in workflow order
  - Docs and fixtures are alphabetical; tests follow the pipeline
  - Read a file's documentation before its code and its tests afterward
- Compressed snapshots, large raw exports, and paired notebook JSON have no
  separate reading time; inspect their summaries or paired Python source

| Read | File | Kind | Lines | Mins | Changed | Docs | Tests |
| :--- | :--- | :--- | ----: | ---: | :------ | :--- | :---- |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_name.sh` | code | 12 | 1 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/version.sh` | code | 28 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents_utils.py` | code | 736 | 37 | yes | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/test_benchmarking_agents_utils.py` |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents.API.py` | code | 139 | 7 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/test_docker_template.py` |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents.example.py` | code | 178 | 9 | yes | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/test_docker_template.py` |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/fetch_leaderboards.py` | code | 106 | 6 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_build.sh` | code | 40 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_jupyter.sh` | code | 90 | 5 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/run_jupyter.sh` | code | 35 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_cmd.sh` | code | 52 | 3 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_bash.sh` | code | 38 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_exec.sh` | code | 25 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_clean.sh` | code | 26 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_push.sh` | code | 25 | 2 | no | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/README.md` | doc | 341 | 12 | yes | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/docker_scripts.README.md` | doc | 887 | 30 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/plan.md` | doc | 415 | 14 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/__init__.py` | test | 0 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test__from_json.test1/input/rows.json` | test | 1 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test__from_json.test1/input/rows.json.gz` | test | compressed | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test1/input/raw/gaia_results.json.gz` | test | compressed | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test1/input/raw/provenance.json` | test | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test1/input/raw/swe_bench_leaderboards.json` | test | 37 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test2/input/raw/gaia_results.json.gz` | test | compressed | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test2/input/raw/provenance.json` | test | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test2/input/raw/swe_bench_leaderboards.json` | test | 37 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test3/input/raw/gaia_results.json.gz` | test | compressed | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test3/input/raw/provenance.json` | test | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_build_scores_table.test3/input/raw/swe_bench_leaderboards.json` | test | 37 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_gaia.test1/input/gaia_results.json` | test | 26 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_gaia.test2/input/gaia_results.json` | test | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_gaia.test3/input/gaia_results.json` | test | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_gaia.test4/input/gaia_results.json` | test | 26 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_gaia.test5/input/gaia_results.json` | test | 1 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_gaia.test6/input/gaia_results.json` | test | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_swe_bench.test1/input/leaderboards.json` | test | 58 | 2 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_swe_bench.test2/input/leaderboards.json` | test | 17 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_load_swe_bench.test3/input/leaderboards.json` | test | 16 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/outcomes/Test_make_provenance_entry.test1/input/sample.txt` | test | 1 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/test_benchmarking_agents_utils.py` | test | 782 | 20 | yes | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/test/test_docker_template.py` | test | 46 | 2 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/.dockerignore` | data | 143 | 5 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/Dockerfile` | data | 138 | 5 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/bashrc` | data | 1 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents.API.ipynb` | data | 203 | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/benchmarking_agents.example.ipynb` | data | 933 | - | yes | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/data/raw/gaia_results.json.gz` | data | compressed | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/data/raw/provenance.json` | data | 14 | 1 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/data/raw/swe_bench_leaderboards.json` | data | 4874 | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/data/scores.csv.gz` | data | compressed | - | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/etc_sudoers` | data | 31 | 2 | no | - | - |
| [ ] | `class_project/msml610/Fall2026/projects/UmdTask934_MSML610_Fall2026_Benchmarking_Data_Science_Agents/requirements.txt` | data | 7 | 1 | no | - | - |

- **Skipped**: build logs, runtime `*.log` files, `tmp.*` diagnostics, caches,
  and symlinks; these are not source or data artifacts to review
- Scripts can create log files beside their sources; ignore those logs
- Shell wrappers share their infrastructure tests outside this project directory
