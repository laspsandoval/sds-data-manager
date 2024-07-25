"""Test the IAlirt ingest lambda function."""

import os

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_dynamodb

from sds_data_manager.lambda_code.IAlirtCode.ialirt_ingest import lambda_handler


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
                {"AttributeName": "reset_number#met", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "reset_number#met", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield table


@pytest.fixture()
def populate_table(table):
    """Populate DynamoDB table."""
    items = [
        {
            "reset_number#met": "0#2025-07-11T12:34:56Z",
            "packet_blob": b"binary_data_string",
        },
        {
            "reset_number#met": "0#2025-07-12T12:34:57Z",
            "packet_blob": b"binary_data_string",
        },
    ]
    for item in items:
        table.put_item(Item=item)

    return item


def test_lambda_handler(dynamodb_table):
    """Test the lambda_handler function."""
    # Mock event data
    event = {"detail": {"object": {"key": "path/to/s3/object/file.txt"}}}

    lambda_handler(event, {})

    table = dynamodb_table
    response = table.get_item(
        Key={
            "reset_number#met": "0#2025-07-11T12:34:56Z",
        }
    )
    item = response.get("Item")

    assert item is not None
    assert item["reset_number#met"] == "0#2025-07-11T12:34:56Z"
    assert item["packet_blob"] == b"binary_data_string"


def test_query_by_met(table, populate_table):
    """Test to query irregular packet length."""
    response = table.query(
        KeyConditionExpression=Key("reset_number#met").eq("0#2025-07-12T12:34:57Z")
    )

    items = response["Items"]
    assert items[0]["reset_number#met"] == "0#2025-07-12T12:34:57Z"
