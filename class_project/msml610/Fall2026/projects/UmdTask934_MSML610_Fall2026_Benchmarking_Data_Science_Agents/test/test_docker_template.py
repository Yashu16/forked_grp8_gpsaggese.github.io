"""Tests for the benchmarking data science agents Docker notebooks."""

import logging

import pytest

import helpers.hdocker_tests as hdoctest

_LOG = logging.getLogger(__name__)


# #############################################################################
# Test_docker
# #############################################################################


class Test_docker(hdoctest.DockerTestCase):
    """
    Run all Docker tests for the benchmarking data science agents project.
    """

    _test_file = __file__

    @pytest.mark.slow
    def test1(self) -> None:
        """
        Test that `benchmarking_agents.example.ipynb` runs without error inside Docker.
        """
        # Prepare inputs.
        notebook_name = "benchmarking_agents.example.ipynb"
        # Run test.
        self.run_notebook(
            notebook_name, use_docker_cmd=True, generate_html=False
        )

    @pytest.mark.slow
    def test2(self) -> None:
        """
        Test that `benchmarking_agents.API.ipynb` runs without error inside Docker.
        """
        # Prepare inputs.
        notebook_name = "benchmarking_agents.API.ipynb"
        # Run test.
        self.run_notebook(
            notebook_name, use_docker_cmd=True, generate_html=False
        )
