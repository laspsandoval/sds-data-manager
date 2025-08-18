"""Tests scheduled job config reader."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sds_data_manager.constructs import scheduled_job_config_reader
from sds_data_manager.constructs.scheduled_job_config_reader import ScheduledJobInfo


def test_scheduled_job_config_reader():
    """Tests the config reader."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_scheduled_jobs_config.csv"
        comment_line = "# this is a comment\n"
        job_1 = "cron(20 6 * * ? *), glows, l3b, descriptor1\n"
        empty_line = "\n"
        job_2 = "cron(20 14 * * ? *), glows, l3c, descriptor2"

        config_path.write_text(
            comment_line + job_1 + empty_line + job_2, encoding="utf-8"
        )
        with patch.object(scheduled_job_config_reader, "CONFIG_PATH", new=config_path):
            scheduled_jobs = scheduled_job_config_reader.read_scheduled_job_config()
            assert scheduled_jobs == [
                ScheduledJobInfo("cron(20 6 * * ? *)", "glows", "l3b", "descriptor1"),
                ScheduledJobInfo("cron(20 14 * * ? *)", "glows", "l3c", "descriptor2"),
            ]


def test_read_scheduled_job_config_throws_exception_for_unknown_instrument():
    """Tests config reader.

    Asserts that the config reader throws an
    exception with an unrecognized instrument.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_scheduled_jobs_config.csv"
        csv_line1 = "# this is a comment\n"
        csv_line2 = "cron(20 6 * * ? *), swapeeee, l3b, sci\n"

        config_path.write_text(csv_line1 + csv_line2, encoding="utf-8")
        with patch.object(scheduled_job_config_reader, "CONFIG_PATH", new=config_path):
            with pytest.raises(ValueError, "Invalid instrument: swapeeee"):
                scheduled_job_config_reader.read_scheduled_job_config()


def test_read_scheduled_job_config_throws_exception_for_wrong_number_of_fields():
    """Tests config reader.

    Asserts that the config reader throws an
    exception with a wrong number of fields.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_scheduled_jobs_config.csv"
        comment = "# this is a comment\n"

        cases = ["swapi, l3b, sci\n", "cron(20 6 * * ? *), swapi, l3b, sci, extra\n"]

        for case in cases:
            config_path.write_text(comment + case, encoding="utf-8")
            with patch.object(
                scheduled_job_config_reader, "CONFIG_PATH", new=config_path
            ):
                message = (
                    f"Each scheduled job should have ['schedule', 'instrument', "
                    f"'data_level', 'descriptor']\nCurrent line: {case}"
                )
                with pytest.raises(ValueError, match=message):
                    scheduled_job_config_reader.read_scheduled_job_config()


def test_read_scheduled_job_config_throws_exception_for_unknown_data_level():
    """Tests config reader.

    Asserts that the config reader throws an
    exception with an unrecognized data_level.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_scheduled_jobs_config.csv"
        csv_line1 = "# this is a comment\n"
        csv_line2 = "cron(20 6 * * ? *), swapi, l3bc, sci\n"

        config_path.write_text(csv_line1 + csv_line2, encoding="utf-8")

        with patch.object(scheduled_job_config_reader, "CONFIG_PATH", new=config_path):
            with pytest.raises(ValueError, "Invalid data level: l3bc"):
                scheduled_job_config_reader.read_scheduled_job_config()
