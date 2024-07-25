"""Test the IAlirt ingest lambda function."""

import os

import boto3
import pytest
from moto import mock_dynamodb

from sds_data_manager.lambda_code.ialirt_ingest_lambda.ialirt_ingest import (
    lambda_handler,
)


@pytest.fixture()
def dynamodb_table():
    """Create a DynamoDB table for testing."""
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
    os.environ["TABLE_NAME"] = "test_table"

    with mock_dynamodb():
        # Create the DynamoDB resource
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")

        # Create the DynamoDB table
        table_name = os.environ["TABLE_NAME"]
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield table


def test_lambda_handler(dynamodb_table):
    """Test the lambda_handler function."""
    # Mock event data
    event = {"detail": {"object": {"key": "path/to/s3/object/file.txt"}}}

    lambda_handler(event, {})

    table = dynamodb_table
    response = table.get_item(
        Key={
            "sct_vtcw_reset#sct_vtcw": "0#2025-07-11T12:34:56Z",
        }
    )
    item = response.get("Item")

    assert item is not None
    assert item["sct_vtcw_reset#sct_vtcw"] == "0#2025-07-11T12:34:56Z"
    assert item["packet_blob"] == b"binary_data_string"
