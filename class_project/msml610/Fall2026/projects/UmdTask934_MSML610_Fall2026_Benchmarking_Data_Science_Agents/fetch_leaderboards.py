#!/usr/bin/env python
"""
Download the published SWE-bench and GAIA leaderboard results.

The data comes from:
- `SWE-bench/swe-bench.github.io`, file `data/leaderboards.json`, at a fixed
  commit
- The Hugging Face dataset `gaia-benchmark/results_public` (config `2023`),
  through the datasets-server, which serves its latest revision

The script saves slim snapshots plus `provenance.json` (URL, revision, download
date and sha256 of each file) under `<dst_dir>/raw/`. Only this script needs
internet. The notebooks and tests read the saved files.

# Usage Example
- Download the data into `data`, replacing the current files:
> fetch_leaderboards.py --dst_dir data --overwrite
- Use a different commit of `SWE-bench/swe-bench.github.io`:
> fetch_leaderboards.py --dst_dir data --overwrite --swe_bench_sha <commit>

Import as:

import fetch_leaderboards as fetlead
"""

import argparse
import logging
import os

import helpers.hdbg as hdbg
import helpers.hio as hio
import helpers.hparser as hparser
import helpers.hselect_input_output as hseinout

import benchmarking_agents_utils as bagutil

_LOG = logging.getLogger(__name__)


def _parse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=hparser.CustomHelpFormatter,
    )
    hseinout.add_dst_dir_arg(
        parser, dst_dir_required=False, dst_dir_default="data"
    )
    parser.add_argument(
        "--swe_bench_sha",
        action="store",
        default=bagutil.SWE_BENCH_SITE_SHA,
        help="Commit of `SWE-bench/swe-bench.github.io` to read from",
    )
    parser.add_argument(
        "--gaia_revision",
        action="store",
        default=bagutil.GAIA_REVISION,
        help="Expected revision of `gaia-benchmark/results_public`",
    )
    hparser.add_verbosity_arg(parser)
    return parser


def _main(parser: argparse.ArgumentParser) -> None:
    args = parser.parse_args()
    hdbg.init_logger(verbosity=args.log_level, use_exec_path=True)
    dst_dir = hseinout.parse_dst_dir_arg(args)
    raw_dir = os.path.join(dst_dir, "raw")
    hio.create_dir(raw_dir, incremental=True)
    # Download the snapshots.
    provenance = {
        bagutil.SWE_BENCH_FILE: bagutil.fetch_swe_bench(
            raw_dir, sha=args.swe_bench_sha
        ),
        bagutil.GAIA_FILE: bagutil.fetch_gaia(
            raw_dir, revision=args.gaia_revision
        ),
    }
    # Save where they came from.
    file_name = os.path.join(raw_dir, bagutil.PROVENANCE_FILE)
    hio.to_json(file_name, provenance)
    _LOG.info("Saved the snapshots and their provenance in '%s'", raw_dir)


if __name__ == "__main__":
    _main(_parse())
