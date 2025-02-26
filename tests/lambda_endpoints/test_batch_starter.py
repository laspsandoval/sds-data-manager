"""Tests the batch starter."""

import json
import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

import pytest
from sqlalchemy.exc import IntegrityError

from sds_data_manager.lambda_code.SDSCode.database import models
from sds_data_manager.lambda_code.SDSCode.database.models import (
    ProcessingJob,
    ScienceFiles,
)
from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas import batch_starter
from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas.batch_starter import (
    IMAPDependencyFinderError,
    _get_dependencies,
    get_file,
    is_job_in_processing_table,
    lambda_handler,
)

from .conftest import POSTGRES_AVAILABLE


def urlopen_side_effect(url):
    """Create a list of dependencies based on the api request url.

    Parameters
    ----------
    url : str
       The request url

    Returns
    -------
    unittest.mock.MagicMock
       A mock context manager returning a HTTP response with the expected dependencies.
    """
    mock_dependencies = {"data_source": "swe", "descriptor": "sci"}

    if "l0" in url and "DOWNSTREAM" in url:
        mock_dependencies["data_type"] = "l1a"
    elif "l1a" in url and "DOWNSTREAM" in url:
        mock_dependencies["data_type"] = "l1b"
    else:
        mock_dependencies["data_type"] = "l0"
        mock_dependencies["descriptor"] = "raw"

    # Create a mock response object that supports context manager
    mock_response = MagicMock()
    mock_context_manager = MagicMock()
    mock_response.read.return_value = json.dumps([mock_dependencies]).encode("utf-8")

    # Mock the context manager and return it
    mock_context_manager.__enter__.return_value = mock_response

    return mock_context_manager


@pytest.fixture()
def mock_urlopen():
    """Mock urlopen to return a list of dependency dictionaries.

    Yields
    ------
    mock_urlopen : unittest.mock.MagicMock
        Mock object for ``urlopen``
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urlopen_side_effect
        yield mock_urlopen


def _populate_file_catalog(session):
    """Add records to the ScienceFiles table."""
    # Setup: Add records to the database
    test_records = [
        ScienceFiles(
            file_path="/path/to/file1",
            instrument="ultra",
            data_level="l2",
            descriptor="sci",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/file2",
            instrument="hit",
            data_level="l0",
            descriptor="raw",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/file3",
            instrument="swe",
            data_level="l0",
            descriptor="raw",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/file4",
            instrument="swe",
            data_level="l1a",
            descriptor="sci",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        # Adding files to test for duplicate job
        ScienceFiles(
            file_path="/path/to/file5",
            instrument="lo",
            data_level="l1a",
            descriptor="de",
            start_date=datetime(2010, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/file6",
            instrument="lo",
            data_level="l1a",
            descriptor="spin",
            start_date=datetime(2010, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
    ]
    session.add_all(test_records)
    session.commit()


def _populate_processing_table(session):
    """Add test data to database."""
    # Add an inprogress record to the processing table
    # At the time of job kickoff, we only have these written to the table
    record = ProcessingJob(
        status=models.Status.INPROGRESS,
        instrument="lo",
        data_level="l1b",
        descriptor="de",
        start_date=datetime(2010, 1, 1),
        version="v001",
    )
    session.add(record)
    session.commit()


def test_get_file(session):
    """Tests the get_file function."""
    _populate_file_catalog(session)

    record = get_file(
        session,
        instrument="ultra",
        data_level="l2",
        descriptor="sci",
        start_date="20240101",
        version="v001",
    )

    assert record.instrument == "ultra"
    assert record.data_level == "l2"
    assert record.descriptor == "sci"
    assert record.start_date == datetime(2024, 1, 1)
    assert record.version == "v001"

    # Non-existent record should return None
    record = get_file(
        session,
        instrument="ultra",
        data_level="l2",
        descriptor="sci",
        start_date="20000101",
        version="v001",
    )
    assert record is None


def test_lambda_handler(
    session,
    mock_urlopen: unittest.mock.MagicMock,
):
    """Tests ``lambda_handler`` function."""
    _populate_file_catalog(session)

    events = {
        "Records": [
            {
                "body": '{"detail": '
                '{"object": {"key": "imap_swe_l0_raw_20240101_v001.pkts"}}'
                "}"
            }
        ]
    }

    context = {"context": "sample_context"}
    with patch.object(batch_starter, "BATCH_CLIENT", Mock()) as mock_batch_client:
        lambda_handler(events, context)
        mock_batch_client.submit_job.assert_called_once()

        # Submit a second job with the same file as input which will try to kick
        # off a duplicate job. We expect the submit_job method to not be called
        # so make sure it is still only called once from our previous iteration.
        lambda_handler(events, context)
        mock_batch_client.submit_job.assert_called_once()


def test_lambda_handler_multiple_events(session, mock_urlopen):
    """Tests ``lambda_handler`` function with multiple events."""
    _populate_file_catalog(session)

    # Test Multiple Events:

    multiple_events = {
        "Records": [
            {
                "body": '{"detail": '
                '{"object": {"key": "imap_swe_l0_raw_20240101_v001.pkts"}}'
                "}"
            },
            {
                "body": '{"detail": '
                '{"object": {"key": "imap_swe_l1a_sci_20240101_v001.cdf"}}'
                "}"
            },
        ]
    }
    context = {"context": "sample_context"}
    with patch.object(batch_starter, "BATCH_CLIENT", Mock()) as mock_batch_client:
        lambda_handler(multiple_events, context)
        assert mock_batch_client.submit_job.call_count == 2


def test_spice_file():
    """Tests ``lambda_handler`` function with spice file."""
    events = {
        "Records": [
            {
                "body": '{"detail": '
                '{"object": {"key": "imap_yyyy_doy_yyyy_doy.spin.csv"}}'
                "}"
            }
        ]
    }

    context = {"context": "sample_context"}

    # Test that value error is raised for SPICE file right now.
    # TODO: undo this and add correct tests when it's implemented.
    with pytest.raises(
        ValueError,
        match="File handling imap_yyyy_doy_yyyy_doy.spin.csv is not implemented yet",
    ):
        lambda_handler(events, context)


def test_is_job_in_status_table(session):
    """Test the ``is_job_in_status_table`` function."""
    _populate_processing_table(session)
    # query the processing table if this job is already in progress
    result = is_job_in_processing_table(
        session=session,
        instrument="lo",
        data_level="l1b",
        descriptor="de",
        start_date="20100101",
        version="v001",
    )

    assert result

    result = is_job_in_processing_table(
        session=session,
        instrument="swapi",
        data_level="l1b",
        descriptor="sci",
        start_date="20100101",
        version="v001",
    )
    assert not result


@pytest.mark.skipif(
    not POSTGRES_AVAILABLE, reason="Only postgres supports partial unique indexes."
)
# Loop over all combinations of status attempts that should fail
@pytest.mark.parametrize(
    "first_status", [models.Status.INPROGRESS, models.Status.SUCCEEDED]
)
@pytest.mark.parametrize(
    "second_status", [models.Status.INPROGRESS, models.Status.SUCCEEDED]
)
def test_duplicate_job(session, first_status, second_status):
    """Multiple jobs in progress should raise an IntegrityError."""
    # Add some initial FAILED entries to the processing table
    # These should not be a part of the unique constraint
    for _ in range(3):
        session.add(
            ProcessingJob(
                status=models.Status.FAILED,
                instrument="lo",
                data_level="l1b",
                descriptor="de",
                start_date=datetime(2010, 1, 1),
                version="v001",
            )
        )
    session.commit()
    assert session.query(ProcessingJob).count() == 3

    record = ProcessingJob(
        status=first_status,
        instrument="lo",
        data_level="l1b",
        descriptor="de",
        start_date=datetime(2010, 1, 1),
        version="v001",
    )
    session.add(record)
    session.commit()
    assert session.query(ProcessingJob).count() == 4

    duplicate = ProcessingJob(
        status=second_status,
        instrument="lo",
        data_level="l1b",
        descriptor="de",
        start_date=datetime(2010, 1, 1),
        version="v001",
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.commit()
    # After an error, we need to rollback the commit
    session.rollback()

    # Now we should still only have 4 items in the table
    assert session.query(ProcessingJob).count() == 4

    # We can add another FAILED status without issue
    record = ProcessingJob(
        status=models.Status.FAILED,
        instrument="lo",
        data_level="l1b",
        descriptor="de",
        start_date=datetime(2010, 1, 1),
        version="v001",
    )
    session.add(record)
    session.commit()
    assert session.query(ProcessingJob).count() == 5


def test_api_request_error(mock_urlopen: unittest.mock.MagicMock):
    """Test that invalid URLs raise an appropriate HTTPError or URLError.

    Parameters
    ----------
    mock_urlopen : unittest.mock.MagicMock
        Mock object for ``urlopen``
    """
    dependency_event_msg = {
        "data_source": "swe",
        "data_type": "l1a",
        "descriptor": "sci",
        "dependency_type": "UPSTREAM",
        "relationship": "HARD",
    }
    # Set up the mock to raise an HTTPError
    mock_urlopen.side_effect = HTTPError(
        url="http://example.com", code=404, msg="Not Found", hdrs={}, fp=BytesIO()
    )
    with pytest.raises(IMAPDependencyFinderError, match="HTTP Error"):
        _get_dependencies(dependency_event_msg)

    # Set up the mock to raise a URLError
    mock_urlopen.side_effect = URLError(reason="Not Found")
    with pytest.raises(IMAPDependencyFinderError, match="URL Error"):
        _get_dependencies(dependency_event_msg)
