"""Functions for triggering a processing job on a schedule."""

import datetime
import logging

from imap_data_access import ProcessingInputCollection

from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas import batch_starter

from ..database import database as db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def scheduled_processing_event(session, events):
    """Process events triggerd by EventBridge rules.

    Parameters
    ----------
    session : orm session
        Database session.
    events : dict
        Event input from an Event Bridge rule.
    """
    batch_starter.try_to_submit_job(
        session,
        events["scheduled"],
        datetime.datetime(2000, 1, 1),
        "v001",
        ProcessingInputCollection().serialize(),
    )


def lambda_handler(events, context):
    """Lambda handler.

    This lambda is triggered on a cron schedule.
    The event should contain a 'scheduled' field
    which contains the job instrument, data_level,
    and descriptor.

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
