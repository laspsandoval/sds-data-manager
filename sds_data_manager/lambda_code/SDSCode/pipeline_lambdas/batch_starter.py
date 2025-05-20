"""Functions for supporting the batch starter component of the architecture."""

import datetime
import json
import logging
from dataclasses import dataclass
from datetime import datetime as dt

import boto3
import imap_data_access
from imap_data_access import (
    AncillaryFilePath,
    ScienceFilePath,
    SPICEFilePath,
)
from imap_data_access.processing_input import (
    ProcessingInputCollection,
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..database import database as db
from ..database import models
from . import dependency
from .dependency import DependencyConfig, get_jobs

# import dependency

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a batch client
BATCH_CLIENT = boto3.client("batch", region_name="us-west-2")

SPECIAL_CASE_JOBS = [
    {
        "data_source": "hi",
        "data_type": "l3",
        "descriptor": "h90-ena-h-sf-sp-full-hae-4deg-6mo",
        "relationship": "HARD",
    },
    {
        "data_source": "lo",
        "data_type": "l3",
        "descriptor": "ilo-ena-h-sf-sp-full-hae-4deg-6mo",
        "relationship": "HARD",
    },
    {
        "data_source": "ultra",
        "data_type": "l3",
        "descriptor": "u90-spx-hsf-sp-full-hae-nside8-3mo",
        "relationship": "HARD",
    },
    {
        "data_source": "idex",
        "data_type": "l2b",
        "descriptor": "sci-1week",
        "relationship": "HARD",
    },
]


@dataclass
class Cadence:
    """Valid cadences for processing jobs triggered by cron jobs.

    Valid cadences can be in either months or years
    """

    months3: str = "3mo"
    months6: str = "6mo"
    years1: str = "1yr"

    @property
    def valid_source(self) -> list[str]:
        """Get all Cadences.

        Returns
        -------
        list[str]
            list of valid cadences.
        """
        return [self.years1, self.months3, self.months6]

    @property
    def days(self) -> dict:
        """Cadence to days.

        Returns
        -------
        dict
            Cadence values in days.
        """
        return {self.years1: 365, self.months3: 90, self.months6: 180}


def determine_job_version(
    session: db.Session,
    instrument: str,
    data_level: str,
    descriptor: str,
    start_date: datetime,
) -> str:
    """Return the maximum existing file version in the pipeline increased by one.

    Parameters
    ----------
    session : orm session
        Database session.
    instrument : str
        Instrument.
    data_level : str
        Data level.
    descriptor : str
        Data descriptor.
    start_date : datetime
        Start date.

    Returns
    -------
     str
        The highest version number.
    """

    def filter_conditions(table):
        # Filter conditions for the query
        conditions = [
            table.instrument == instrument,
            table.data_level == data_level,
            table.descriptor == descriptor,
            table.start_date == start_date,
        ]
        if table == models.ProcessingJob:
            conditions.append(
                table.status.in_(
                    [models.Status.INPROGRESS.value, models.Status.SUCCEEDED.value]
                )
            )
        return conditions

    # First check to see if there are any jobs in progress and get the max version
    max_version = (
        session.query(func.max(models.ProcessingJob.version)).filter(
            *filter_conditions(models.ProcessingJob)
        )
    ).scalar()
    # If the descriptor is "all", we should only check the processing job table. The
    # ScienceFiles table does not have descriptors of "all" since the products
    # produced will have their own specific descriptors.
    if descriptor == "all":
        return f"v{int(max_version[1:]) + 1:03d}" if max_version else "v001"
    # If no jobs are in progress, check the science files table for the max version.
    if not max_version:
        max_version = (
            session.query(func.max(models.ScienceFiles.version)).filter(
                *filter_conditions(models.ScienceFiles)
            )
        ).scalar()
    # Bump the version number. "V001" will be returned if max_version is None.
    return f"v{int(max_version[1:]) + 1:03d}" if max_version else "v001"


def handle_special_case_jobs(session, job_node, start_date, end_date):
    """Handle special case jobs that require more specific dependency querying.

    Parameters
    ----------
    session : orm session
        Database session.
    job_node : dict
        job node to get the potential jobs from.
    start_date : str
        Start date to query the data.
    end_date : str
        End date to query the data.
    """

    def find_most_recent_dep_start_date(dep, start_date):
        # Find the most recent start_date that matches the filters
        return (
            session.query(func.max(models.ScienceFiles.start_date))
            .filter(
                models.ScienceFiles.instrument == dep["data_source"],
                models.ScienceFiles.data_level == dep["data_type"],
                models.ScienceFiles.descriptor == dep["descriptor"],
                models.ScienceFiles.start_date <= start_date,
            )
            .scalar()
        )

    start_date_dt = dt.strptime(start_date, "%Y%m%d")
    if job_node["data_source"] == "idex":
        # IDEX l2b needs all the l1b evt datasets since the last l2b job.
        # We need to find the most recent l2b job (before the current start_date from
        # the trigger file which is a l2a file).
        one_day = datetime.timedelta(days=1)
        new_start_date = (
            find_most_recent_dep_start_date(job_node, start_date_dt - one_day) + one_day
        )
        new_start_date = new_start_date.strftime("%Y%m%d")
        # Add one day to the most recent start date because we only want data after.
        # Submit the IDEX l2b job with the new start date and the original end date.
        submit_all_jobs(
            session, job_node, new_start_date, end_date, filter_dependencies=False
        )
    else:
        # Each of these maps has a l2 map and corresponding glows l3e files.
        # To run this job, we need to find the most recent l2 map file and use that
        # date range to query the glows l3e files.
        deps = get_jobs(
            "UPSTREAM",
            "HARD",
            job_node["data_source"],
            job_node["data_type"],
            job_node["descriptor"],
        )
        # Get the l2 upstream dependency. There should only be one
        l2_dep = next(dep for dep in deps if dep["data_type"] == "l2")
        # Find the most recent l2 map file
        new_start_date = find_most_recent_dep_start_date(l2_dep, start_date_dt)
        # Get the number of days the map was created for
        map_days = Cadence().days[job_node["descriptor"].split("-")[-1]]
        new_end_date = start_date_dt + datetime.timedelta(days=map_days)
        submit_all_jobs(
            session,
            job_node,
            new_start_date.strftime("%Y%m%d"),
            new_end_date.strftime("%Y%m%d"),
            filter_dependencies=False,
        )


def try_to_submit_job(
    session: db.Session,
    job_info: dict,
    start_date: datetime,
    version: str,
    upstream_dependencies: ProcessingInputCollection,
):
    """Try to submit a batch job with the given job information.

    Parameters
    ----------
    session : orm session
        Database session.
    job_info : dict
        Dictionary containing components with dates and versions appended.
    start_date : datetime
        Start date of the data.
    version : str
        Version of the job.
    upstream_dependencies : ProcessingInputCollection
        Input collection of upstream dependencies.
    """
    instrument = job_info["data_source"]
    data_level = job_info["data_type"]
    descriptor = job_info["descriptor"]
    start_date_str = dt.strftime(start_date, "%Y%m%d")

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
    # what batch job expects.
    # TODO: do we need a reprocessing column to indicate if this is a reprocessing job?
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
        f"{upstream_dependencies.serialize()}",
        "--upload-to-sdc",
    ]

    # NOTE: The batch job name should contain only alphanumeric characters and hyphens
    # E.g. "codice-l1a-sci-job-1"
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


def submit_all_jobs(session, job_node, start_date, end_date, filter_dependencies=True):
    """Submit all jobs for the given job and upstream dependencies.

    Parameters
    ----------
    session : orm session
        Database session.
    job_node : dict
        job node to get the potential jobs from.
    start_date : str
        Start date to query the data.
    end_date : str
        End date to query the data.
    filter_dependencies : bool
        If True, filter the upstream dependencies to only include the files valid for
        upstream primary science start_date. For cadence jobs, we should never filter
        the upstream dependencies because we want all the files found within the cadence
        job range. For IDEX l2b, this is a special case where we need the last 7 days
        of housekeeping event message data, so we should not filter the dependencies.

    """
    # Submit downstream jobs for each upstream primary science dependency file.
    # Find the files that this job depends on
    upstream_dependencies = dependency.get_jobs(
        data_source=job_node["data_source"],
        data_type=job_node["data_type"],
        descriptor=job_node["descriptor"],
        dependency_type="UPSTREAM",
        relationship="ALL",
        start_date=start_date,
        end_date=end_date,
    )
    if not upstream_dependencies:
        return

    logger.info(f"All required dependencies found for the dependency: {job_node}")
    # Find the first science processingInput that has the same source as the
    # potential job. Use this to determine the start date.
    primary_science = upstream_dependencies.get_science_inputs(job_node["data_source"])[
        0
    ]
    num_jobs = len(primary_science.imap_file_paths)
    logger.info(f"Found {num_jobs} jobs to process.")
    for filepath in primary_science.imap_file_paths:
        job_start_date = dt.strptime(filepath.start_date, "%Y%m%d")
        job_version = determine_job_version(
            session=session,
            instrument=job_node["data_source"],
            descriptor=job_node["descriptor"],
            start_date=job_start_date,
            data_level=job_node["data_type"],
        )
        # If there is only one file to process, then we can use upstream dependencies
        # that have already been queried.
        if num_jobs > 1 or filter_dependencies:
            # Query for upstream files only needed for this job with using the
            # start date of the primary science file.
            upstream_deps_for_job = dependency.get_jobs(
                data_source=job_node["data_source"],
                data_type=job_node["data_type"],
                descriptor=job_node["descriptor"],
                dependency_type="UPSTREAM",
                relationship="ALL",
                start_date=filepath.start_date,
                end_date=filepath.start_date,
            )
        else:
            upstream_deps_for_job = upstream_dependencies
        try_to_submit_job(
            session, job_node, job_start_date, job_version, upstream_deps_for_job
        )


def s3_processing_event(session, events):
    """Process SQS events that were triggered by S3 file arrivals.

    Parameters
    ----------
    session : orm session
        Database session.
    events : dict
        SQS event input.
    """
    # Since the SQS events can be batched together, we need to loop through
    # each event. In this loop, "event" represents one file landing.

    # Check for glows l3e files. They might come in large groupings from the sqs because
    # glows l3 processing might produce ~30 files at once. We only want one to trigger
    # one downstream l3 survival probability map.
    triggered_from_glows_l3e = False
    for event in events["Records"]:
        # Event details:
        logger.info(f"Individual event: {event}")
        body = json.loads(event["body"])

        filename = body["detail"]["object"]["key"]
        logger.info(f"Retrieved filename: {filename}")

        file_obj = imap_data_access.file_validation.generate_imap_file_path(filename)
        input_obj = imap_data_access.processing_input.generate_imap_input(filename)

        if input_obj.source == "glows" and input_obj.data_type == "l3e":
            if triggered_from_glows_l3e:
                logger.info(
                    f"Already tried to submit job from a glows l3e file."
                    f"Skipping trigger from filename {filename}"
                )
                continue
            else:
                triggered_from_glows_l3e = True

        if isinstance(file_obj, SPICEFilePath):
            # Set the start and end dates for the upstream event message.
            # TODO: fix date range if/when repoint file ingestion event is
            # passed to batch starter to kickoff HARD or SOFT_TRIGGER downstream jobs.
            # Convert datetime object to string of format YYYYMMDD
            start_date = file_obj.spice_metadata["start_date"].strftime("%Y%m%d")
            end_date = file_obj.spice_metadata["end_date"].strftime("%Y%m%d")
        elif isinstance(file_obj, ScienceFilePath):
            # Set the start and end dates for the upstream event message
            # TODO: if ENA or glows instrument, then get repoint number from filename
            # and set start date and end date differently.
            start_date = end_date = file_obj.start_date
        elif isinstance(file_obj, AncillaryFilePath):
            # Set the start and end dates for the upstream event message
            start_date = file_obj.start_date
            # Ancillary files can have an end date.
            end_date = getattr(file_obj, "end_date", None)
            # If there is no end date for the ancillary file, then it is implicitly
            # valid through today.
            if not end_date:
                end_date = datetime.today().strftime("%Y%m%d")
        # Potential jobs are the instruments that depend on the current file,
        # which are the downstream dependencies.
        potential_jobs = dependency.get_jobs(
            data_source=input_obj.source,
            descriptor=input_obj.descriptor,
            data_type=input_obj.data_type,
            dependency_type="DOWNSTREAM",
            relationship="HARD",
        )

        # SOFT_TRIGGER dependencies will try to set off processing
        potential_soft_jobs = dependency.get_jobs(
            data_source=input_obj.source,
            descriptor=input_obj.descriptor,
            data_type=input_obj.data_type,
            dependency_type="DOWNSTREAM",
            relationship="SOFT_TRIGGER",
        )
        logger.info(
            f"Potential jobs: {potential_jobs} and potential soft jobs: "
            f"{potential_soft_jobs}"
        )
        if not potential_jobs and not potential_soft_jobs:
            logger.info(f"No downstream dependencies found for the file: {filename}")
            continue
        for job in potential_jobs + potential_soft_jobs:
            if job in SPECIAL_CASE_JOBS:
                handle_special_case_jobs(session, job, start_date, end_date)
            else:
                submit_all_jobs(session, job, start_date, end_date)


def bulk_reprocessing_event(session, events):
    """Process bulk reprocessing event.

    Parameters
    ----------
    session : orm session
        Database session.
    events : dict
        Event input.
    """
    # TODO: We need s3 tag or column in db to track bulk reprocessing
    instrument = events.get("instrument")
    data_level = events.get("data_level")
    descriptor = events.get("descriptor")
    start_date = events.get("start_date")
    end_date = events.get("end_date")
    if not end_date or not start_date:
        raise ValueError(
            "Start date and end date are required for a reprocessing Event."
        )
    if data_level:
        # If data_level is provided, instrument and descriptor are required.
        if not instrument or not descriptor:
            raise ValueError(
                "If data_level is provided, instrument and descriptor are required."
            )
        # we need to find the upstream dependencies for this instrument, data level,
        # and descriptor
        potential_jobs = [
            {
                "data_source": instrument,
                "descriptor": descriptor,
                "data_type": data_level,
            }
        ]
    else:
        # If no instrument is provided, there should be no descriptor or data level.
        if not instrument and descriptor:
            raise ValueError(
                "If descriptor is provided, instrument must also be provided."
            )
        # If data_level is not provided, we need to reprocess all levels.
        # Get the jobs that kick of each pipeline, to trigger processing
        # for all levels.
        potential_jobs = DependencyConfig().kickoff_pipeline_jobs()
        # filter the jobs by instrument and descriptor if provided
        potential_jobs = [
            job
            for job in potential_jobs
            if (
                (job["data_source"] == instrument or not instrument)
                and (job["descriptor"] == descriptor or not descriptor)
            )
        ]

    for job in potential_jobs:
        if job in SPECIAL_CASE_JOBS:
            # TODO fix bulk reprocessing for special cases.
            logger.warning(
                f"bulk reprocessing is currently not supported for unique"
                f" job: {job}. Handling will be added soon."
            )
        else:
            submit_all_jobs(session, job, start_date, end_date)


def lambda_handler(events: dict, context):
    """Lambda handler.

    This lambda is triggered by different events.
    1. Event of a new science or ancillary file arrival from indexer lambda.
        Example event:
            {
                "Records": [
                    {
                        "body": '{"detail": '
                        '{"object": {"key": '
                        '"imap_swe_l1b-in-flight-cal_20240101_v001.cdf"}}'
                        "}"
                    }
                ]
            }
    2. Event of a new science reprocessing.
        Example event: see example above.
    3. Event of a new spice file arrival from spice indexer lambda.
        TODO: This will be implemented in the future.
    4. Event of bulk reprocessing of science.
        Example event:
            {
                "queryStringParameters": {
                    "reprocessing": True,
                    "start_date": <>,
                    "end_date": <>,
                    "instrument": None, optional,
                    "data_level": None, optional,
                    "data_descriptor": None, optional,
                }
            }
    5. Event of a cron job cadence trigger.
        TODO: This will be implemented in the future.
        Example event:
            {
                "cadence": 3months or 7days,
                "instrument": <>,
                "data_level": <>,
                "descriptor": <>
            }

    Parameters
    ----------
    events : dict
        Event input
    context : LambdaContext
        Lambda context object
    """
    logger.info(f"Events: {events}")
    logger.info(f"Context: {context}")

    with db.Session() as session:
        api_event = events.get("queryStringParameters")
        if api_event and api_event.get("reprocessing"):
            # handle reprocessing event
            bulk_reprocessing_event(session, api_event)
        else:
            # handle s3 event from the SQS queue
            s3_processing_event(session, events)
