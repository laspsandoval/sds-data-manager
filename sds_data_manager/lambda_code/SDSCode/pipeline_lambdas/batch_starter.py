"""Functions for supporting the batch starter component of the architecture."""

# ruff: noqa: S310
# potentially unsafe usage of urlopen TODO: are we concerned here?
import contextlib
import json
import logging
import os
import urllib
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import boto3
from imap_data_access import AncillaryFilePath, ScienceFilePath, processing_input
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import database as db
from ..database import models
from .dependency import get_files

# import dependency

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a batch client
BATCH_CLIENT = boto3.client("batch", region_name="us-west-2")


class IMAPDependencyFinderError(Exception):
    """Base class for exceptions in this module."""

    pass


@contextlib.contextmanager
def _get_url_response(url: str):
    """Get the response from a URL.

    This is a helper function to make it easier to handle
    the different types of errors that can occur when
    opening a URL and write out the response body.
    """
    try:
        # Open the URL and yield the response
        with urllib.request.urlopen(url) as response:
            yield response
    except HTTPError as e:
        message = (
            f"HTTP Error: {e.code} - {e.reason}\n"
            f"Server Message: {e.read().decode('utf-8')}"
        )
        raise IMAPDependencyFinderError(message) from e

    except URLError as e:
        message = f"URL Error: {e.reason}"
        raise IMAPDependencyFinderError(message) from e


def _get_dependencies(dependency_events):
    """Return dependencies for the input dependency requirements."""
    base = f"{os.getenv('IMAP_DATA_ACCESS_URL')}/dependency?"
    url = f"{base}{urlencode(dependency_events)}"

    logger.info("Finding dependencies for %s with url %s", dependency_events, url)
    with _get_url_response(url) as response:
        # Retrieve the response as a list of dictionaries containing the dependency
        # information
        dependency_repsonse = response.read().decode("utf-8")
        # Parse the JSON responses
        dependencies = json.loads(dependency_repsonse)
        logger.debug(f"Received dependencies: {dependencies}")

    return dependencies


def is_job_in_processing_table(
    session: db.Session,
    instrument: str,
    descriptor: str,
    data_level: str,
    start_date: datetime,
    version: str,
):
    """Check if the job is already running.

    Parameters
    ----------
    session : orm session
        Database session.
    instrument : str
        Instrument.
    descriptor : str
        Data descriptor.
    data_level : str
        Data level.
    start_date : datetime
        Start date.
    version : str
        Data version.

    Returns
    -------
    bool
        True if a duplicate job is found, False otherwise.
    """
    # check in the processing table if the job is already in progress
    # for this instrument, data level, version, and descriptor
    query = select(models.ProcessingJob.__table__).where(
        models.ProcessingJob.instrument == instrument,
        models.ProcessingJob.descriptor == descriptor,
        models.ProcessingJob.data_level == data_level,
        models.ProcessingJob.start_date == start_date,
        models.ProcessingJob.version == version,
        models.ProcessingJob.status.in_(
            [models.Status.INPROGRESS.value, models.Status.SUCCEEDED.value]
        ),
    )

    results = session.execute(query).all()

    if results:
        return True
    return False


def try_to_submit_job(session, job_info, start_date, version):
    """Try to submit a batch job with the given job information.

    Go through the job information to retrieve all necessary input files
    (upstream dependencies). If any are missing, return. If we have
    all the necessary input files, submit the job to the batch queue.

    Parameters
    ----------
    session : orm session
        Database session.
    job_info : dict
        Dictionary containing components with dates and versions appended.
    start_date : datetime
        Start date of the data.
    version : str
        Version of the data.

    Returns
    -------
    bool
        Whether or not this job is ready to be processed.
    """
    instrument = job_info["data_source"]
    data_level = job_info["data_type"]
    descriptor = job_info["descriptor"]

    start_date_str = datetime.strftime(start_date, "%Y%m%d")

    logger.info("Checking for job in progress before looking for dependencies.")

    if is_job_in_processing_table(
        session=session,
        instrument=instrument,
        descriptor=descriptor,
        start_date=start_date,
        version=version,
        data_level=data_level,
    ):
        logger.info(
            f"Job already in progress for {instrument}, {data_level}, "
            f"{descriptor}, {start_date_str}, {version}"
        )
        return

    # Find the files that this job depends on
    dependency_event_msg = {
        "data_source": instrument,
        "data_type": data_level,
        "descriptor": descriptor,
        "dependency_type": "UPSTREAM",
        "relationship": "HARD",
        "start_date": start_date,
        "version": version,
    }

    upstream_dependencies = _get_dependencies(dependency_event_msg)
    # TODO return if dependency is not found
    #
    logger.info(f"All dependencies found for the job: {job_info}")

    # All of our upstream requirements have been met.
    # Try to insert a record into the Processing Jobs table
    # If this job already exists, then we will get an integrity error
    # and know that some other process has already taken care of it
    processing_job = models.ProcessingJob(
        status=models.Status.INPROGRESS,
        instrument=instrument,
        data_level=data_level,
        descriptor=descriptor,
        start_date=start_date,
        version=version,
    )

    try:
        session.add(processing_job)
        session.commit()
    except IntegrityError:
        logger.info(f"Job already completed or in progress: {processing_job}")
        return

    logger.info(
        f"Wrote job INPROGRESS to Processing Jobs Table with id: {processing_job.id}"
    )

    # Reformat the upstream dependencies from dependency call to match
    # what batch job expects. Change 'data_source' to 'instrument' and
    # 'data_type' to 'data_level'.

    batch_command = [
        "--instrument",
        instrument,
        "--data-level",
        data_level,
        "--descriptor",
        descriptor,
        "--start-date",
        start_date_str,
        "--version",
        version,
        "--dependency",
        f"{upstream_dependencies}",
        "--upload-to-sdc",
    ]

    # NOTE: The batch job name should contain only alphanumeric characters and hyphens
    # Eg. "codice-l1a-sci-job-1"
    # The `processing_job.id` is used later for updating the job processing table
    job_name = f"{instrument}-{data_level}-{descriptor}-job-{processing_job.id}"
    # Get the necessary AWS information
    # NOTE: These are here for easier mocking in tests rather than at the module level
    step = "-l3" if data_level >= "l3" else ""
    job_definition = f"ProcessingJob-{instrument}{step}"
    job_queue = "ProcessingJobQueue"
    BATCH_CLIENT.submit_job(
        jobName=job_name,
        jobQueue=job_queue,
        jobDefinition=job_definition,
        containerOverrides={
            "command": batch_command,
        },
    )
    logger.info(f"Submitted job {job_name} with this command: {batch_command}")


def find_upstream_science_start_dates(
    session, job_info, start_date, version, end_date=None
):
    """Find start dates of upstream science files that a job depends on.

    Parameters
    ----------
    session : orm session
        Database session.
    job_info : dict
        Dictionary containing components with dates and versions appended.
    start_date : datetime
        Start date of the event data.
    version : str
        Version of the event data.
    end_date: datetime, optional
        End date of the event data.

    Returns
    -------
    list[datetime]
        List of start_date datetime objects for the first occurrence of an upstream
        science files
    """
    # Find the files that this job depends on
    upstream_dependencies = _get_dependencies(
        {
            "data_source": job_info["data_source"],
            "data_type": job_info["data_type"],
            "descriptor": job_info["descriptor"],
            "dependency_type": "UPSTREAM",
            "relationship": "HARD",
        }
    )

    instrument = None
    data_level = None
    descriptor = None

    # Only care about the first science dependency
    # All upstream science dependencies have the same start date
    for dep in upstream_dependencies:
        if dep["data_type"] not in ["ancillary", "SPICE"]:
            instrument = dep["data_source"]
            data_level = dep["data_type"]
            descriptor = dep["descriptor"]
            break

    # If no upstream science dependency was found.
    if instrument is None:
        return []
    # Query for science upstream science files
    records = get_files(
        session,
        instrument,
        data_level,
        descriptor,
        start_date,
        version,
        end_date,
        ancillary_upstream=True,
    )
    # Return start dates
    return [record.start_date for record in records]


def get_all_files_to_process(potential_jobs):
    """Get all files that need to be processed."""
    pass


def lambda_handler(events: dict, context):
    """Lambda handler.

    This lambda is triggered by different events.
    1. Event of a new science or ancillary file arrival from indexer lambda.
        Example event:
            {
                "DetailType": "Processed File",
                "Source": "imap.lambda",
                "Detail": {
                    "object": {
                        "key": str,
                        "instrument": str,
                    }
                }
            }
    2. Event of a new spice file arrival from spice indexer lambda.
        TODO: This will be implemented in the future.
    3. Event of a new science reprocessing.
        TODO: This will be implemented in the future.
    4. Event of bulk processing of science in normal processing.
        TODO: This will be implemented in the future.

    Parameters
    ----------
    events : dict
        Event input
    context : LambdaContext
        Lambda context object
    """
    logger.info(f"Events: {events}")
    logger.info(f"Context: {context}")

    # Since the SQS events can be batched together, we need to loop through
    # each event. In this loop, "event" represents one file landing.
    for event in events["Records"]:
        # Event details:
        logger.info(f"Individual event: {event}")
        body = json.loads(event["body"])

        filename = body["detail"]["object"]["key"]
        logger.info(f"Retrieved filename: {filename}")

        # Try to create a science file first
        # TODO replace with Maxine's factory method
        try:
            file_obj = ScienceFilePath(filename)
        except ScienceFilePath.InvalidScienceFileError as e:
            logger.error(str(e))
            try:
                file_obj = AncillaryFilePath(filename)
            except AncillaryFilePath.InvalidAncillaryFileError as e:
                # No science or ancillary file type matched, return an error with the
                # exception message indicating how to fix it to the user
                logger.error(str(e))

                file_obj = None

        if file_obj is None:
            raise ValueError(f"File handling {filename} is not implemented yet")

        # TODO: How to handle repointing

        start_date = file_obj.start_date
        end_date = file_obj.end_date if hasattr(file_obj, "end_date") else None
        version = file_obj.version

        # TODO: handle spice once implemented
        data_type = (
            file_obj.data_level if hasattr(file_obj, "data_level") else "ancillary"
        )

        dependency_event_msg = {
            "data_source": file_obj.instrument,
            "descriptor": file_obj.descriptor,
            "data_type": data_type,
            "dependency_type": "DOWNSTREAM",
            "relationship": "HARD",
            "start_date": start_date,
            "end_date": end_date,
        }
        # Potential jobs are the instruments that depend on the current file,
        # which are the downstream dependencies.
        potential_jobs = _get_dependencies(dependency_event_msg)
        potential_jobs = processing_input.ProcessingInputCollection.deserialize()
        # TODO now get own primary source data.

        # If 'file_obj' is an ancillary file, there could be more than one
        # potential downstream dependency job for a given data_source, data_type, and
        # descriptor.
        # E.g. if imap_swe_l1b-in-flight-cal_20250101-20250105.cdf file arrives,
        # This could potentially trigger multiple swe l1b files that have been waiting
        #    - imap_swe_l1b_sci_20250102.cdf
        #    - imap_swe_l1b_sci_20250103.cdf
        #    - imap_swe_l1b_sci_20250104.cdf

        # To find these jobs, get the first upstream science dependency
        # And query the science table to get all the start times
        # e.g. [20250102, 20250103, 20250104].
        # Then call try_to_submit_job for the dependency, and each of these start times
        with db.Session() as session:
            # Convert start_date to a datetime obj
            start_date = datetime.strptime(start_date, "%Y%m%d")
            if isinstance(file_obj, AncillaryFilePath):
                if end_date:
                    end_date = datetime.strptime(file_obj.end_date, "%Y%m%d")
                for job in potential_jobs:
                    upstream_science_start_dates = get_all_files_to_process(
                        potential_jobs
                    )

                    for upstream_date in upstream_science_start_dates:
                        try_to_submit_job(session, job, upstream_date, version)
            else:
                # Submit job for science file downstream jobs
                for job in potential_jobs:
                    try_to_submit_job(session, job, start_date, version)
