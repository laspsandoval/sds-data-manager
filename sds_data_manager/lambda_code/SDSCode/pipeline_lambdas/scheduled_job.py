"""Functions for triggering a processing job on a schedule."""

import datetime
import logging

from imap_data_access import ProcessingInputCollection

from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas import batch_starter

from ..database import database as db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SCHEDULED_JOBS = {
    # Expected scheduled job structure:
    # "glows": [{
    #     "data_source": "glows",
    #     "data_type": "l3b",
    #     "descriptor": "ion-rate-profile"
    # }],
}


def scheduled_processing_event(session, events):
    """Process events triggerd by EventBridge rules.

    Parameters
    ----------
    session : orm session
        Database session.
    events : dict
        Event input from an Event Bridge rule.
    """
    for job in SCHEDULED_JOBS[events["scheduled"]]:
        batch_starter.try_to_submit_job(
            session,
            job,
            datetime.datetime(2000, 1, 1),
            "v001",
            ProcessingInputCollection().serialize(),
        )


def lambda_handler(events, context):
    """Lambda handler.

    This lambda is triggered on a cron schedule.
    It's passed an ID that is used to look up what
    data product to process as defined in SCHEDULED_JOBS

    Parameters
    ----------
    events : dict
        Event input
    context : LambdaContext
        Lambda context object
    """
    logger.info(f"Events: {events}")

    with db.Session() as session:
        if events.get("scheduled"):
            scheduled_processing_event(session, events)
