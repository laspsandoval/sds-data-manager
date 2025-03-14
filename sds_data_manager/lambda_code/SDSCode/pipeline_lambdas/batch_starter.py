"""Functions for supporting the batch starter component of the architecture."""

# ruff: noqa: S310
# potentially unsafe usage of urlopen TODO: are we concerned here?
import contextlib
import json
import logging
import os
import urllib
from datetime import datetime
from os.path import basename
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import boto3
from imap_data_access import AncillaryFilePath, ScienceFilePath, processing_input
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from ..database import database as db
from ..database import models

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


def get_files(
    session,
    instrument,
    data_type,
    descriptor,
    start_date,
    version,
    end_date=None,
    ancillary_upstream=False,
):
    """Query to database to get ScienceFile or AncillaryFile records.

    Parameters
    ----------
    session : orm session
        Database session.
    instrument : str
        Instrument name.
    data_type : str
        Data type.
    descriptor : str
        Data descriptor.
    start_date : datetime
        Start date of the event data.
    version : str
        Version of the event data.
    end_date: datetime, optional
        End date of the event data.
    ancillary_upstream: bool, optional,
        Determines how start date filtering is queried.
        When True, indicates we are looking for files that are downstream from an
        ancillary file, so we query for files with start dates greater than or equal
        to the ancillary file's start date. When False, we query for files with a match
        to the start time. Default is False.

    Returns
    -------
    records : list[Union[models.ScienceFiles, models.AncillaryFiles]]
        The ScienceFiles or AncillaryFiles records matching the query criteria.
    """
    # TODO can we use query spice/ ancillary/ science api here?
    type_specific_conditions = []
    # TODO replace with enum?
    if data_type == "ancillary":
        table = models.AncillaryFiles
        # Query for ancillary files whose ranges cover the
        # start date.
        # E.g., if the start date is '20250102', the query could return an ancillary
        # file with the date range ('20250101', '20250103')
        type_specific_conditions.append(
            and_(
                table.start_date <= start_date,
                or_(table.end_date >= start_date, table.end_date.is_(None)),
            )
        )
    else:
        table = models.ScienceFiles
        if ancillary_upstream:
            if end_date:
                # Find files that are downstream from an ancillary file
                # Query for science files with a start date later or equal to the
                # ancillary start date and less than the ancillary end date.
                type_specific_conditions.append(
                    and_(
                        models.ScienceFiles.start_date >= start_date,
                        models.ScienceFiles.start_date <= end_date,
                    )
                )
            else:
                # Find files that are downstream from an ancillary file
                # if there is no end date query for science files with dates past or
                # equal the ancillary start date
                type_specific_conditions.append(
                    models.ScienceFiles.start_date >= start_date
                )
        else:
            # Query for science files matching the start date
            type_specific_conditions.append(
                models.ScienceFiles.start_date == start_date
            )

    filter_conditions = [
        table.instrument == instrument,
        table.descriptor == descriptor,
        table.version == version,
        *type_specific_conditions,
    ]

    records = session.query(table).filter(*filter_conditions).all()

    return records


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
    }

    upstream_dependencies = _get_dependencies(dependency_event_msg)

    input_collection = processing_input.ProcessingInputCollection()
    for upstream_dependency in upstream_dependencies:
        upstream_source = upstream_dependency["data_source"]
        upstream_data_type = upstream_dependency["data_type"]
        upstream_descriptor = upstream_dependency["descriptor"]

        records = get_files(
            session,
            upstream_source,
            upstream_data_type,
            upstream_descriptor,
            start_date,
            version,
        )
        if not records:
            logger.info(
                f"Dependency not found: {upstream_source}, "
                f"{upstream_data_type}, "
                f"{upstream_descriptor}, "
                f"{start_date_str}, "
                f"{version}"
            )
            return  # Exit the loop early as we already found a missing dependency
        else:
            filenames = [basename(record.file_path) for record in records]
            if upstream_data_type == "ancillary":
                input_collection.add(processing_input.AncillaryInput(*filenames))
            else:
                input_collection.add(processing_input.ScienceInput(*filenames))

            # TODO handle SPICE input type here

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

    # TODO: change the upstream dependency keys as needed in the future based
    # on needs. Right now, we are keeping same as before to reduce complexity.
    # FYI, upstream_dependencies in the command below should contain these keys:
    #   'instrument',
    #   'data_level',
    #   'descriptor',
    #   'start_date',
    #   'version'
    # Example list of upstream_dependencies in the command below:
    # [
    #   {
    #     'instrument': 'swe',
    #     'data_level': 'l1b',
    #     'descriptor': 'sci',
    #     'start_date': '20231212',
    #     'version': 'v001',
    #   },
    #   {
    #     'instrument': 'sc_attitude',
    #     'data_level': 'spice',
    #     'descriptor': 'historical',
    #     'start_date': '20231212',
    #     'version': '01',
    #   },
    # ]

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
        f"{input_collection.serialize()}",
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

        start_date = datetime.strptime(file_obj.start_date, "%Y%m%d")
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
        }
        # Potential jobs are the instruments that depend on the current file,
        # which are the downstream dependencies.
        potential_jobs = _get_dependencies(dependency_event_msg)

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
            if isinstance(file_obj, AncillaryFilePath):
                end_date = (
                    datetime.strptime(file_obj.end_date, "%Y%m%d")
                    if file_obj.end_date
                    else None
                )

                for job in potential_jobs:
                    upstream_science_start_dates = find_upstream_science_start_dates(
                        session, job, start_date, version, end_date
                    )

                    for upstream_date in upstream_science_start_dates:
                        try_to_submit_job(session, job, upstream_date, version)
            else:
                # Submit job for science file downstream jobs
                for job in potential_jobs:
                    try_to_submit_job(session, job, start_date, version)
