import logging
import os
import boto3
import json

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Create metadata and add it to the database.

    This function is an event handler for s3 ingest bucket.
    It is also used to ingest data to the DynamoDB table.

    Parameters
    ----------
    event : dict
        The JSON formatted document with the data required for the
        lambda function to process
    context : LambdaContext
        This object provides methods and properties that provide
        information about the invocation, function,
        and runtime environment.

    """
    logger.info("Received event: %s", json.dumps(event))

    try:
        # Retrieve the Object name from the event
        s3_filepath = event["detail"]["object"]["key"]
        filename = os.path.basename(s3_filepath)
        logger.info("Retrieved filename: %s", filename)

        item = {
            'packet_filename': filename,
            'sct_vtcw_reset#sct_vtcw': 'example_sort_key',
        }

        table.put_item(Item=item)
        logger.info("Successfully wrote item to DynamoDB: %s", item)

    except Exception as e:
        logger.error("Error processing event: %s", str(e))
        raise
