"""Test the IAlirt ingest lambda function."""

import pytest
from boto3.dynamodb.conditions import Key

from sds_data_manager.lambda_code.IAlirtCode.ialirt_ingest import lambda_handler


@pytest.fixture()
def populate_table(table):
    """Populate DynamoDB table."""
    items = [
        {
            "reset_number#met": "0#123",
            "packet_blob": b"binary_data_string",
        },
        {
            "reset_number#met": "0#124",
            "packet_blob": b"binary_data_string",
        },
    ]
    for item in items:
        table.put_item(Item=item)

    return item


def test_lambda_handler(table):
    """Test the lambda_handler function."""
    # Mock event data
    event = {"detail": {"object": {"key": "path/to/s3/object/file.txt"}}}

    lambda_handler(event, {})

    response = table.get_item(
        Key={
            "reset_number#met": "0#123",
        }
    )
    item = response.get("Item")

    assert item is not None
    assert item["reset_number#met"] == "0#123"
    assert item["packet_blob"] == b"binary_data_string"


def test_query_by_met(table, populate_table):
    """Test to query irregular packet length."""
    response = table.query(KeyConditionExpression=Key("reset_number#met").eq("0#124"))

    items = response["Items"]
    assert items[0]["reset_number#met"] == "0#124"
