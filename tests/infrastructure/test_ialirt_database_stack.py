"""Test the IAlirt database stack."""

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_dynamodb

TABLE_NAME = "imap-packetdata-table"


@pytest.fixture()
def dynamodb():
    """Initialize DynamoDB resource and create table."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                # Partition key
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb
        table.delete()


@pytest.fixture()
def populate_table(dynamodb):
    """Populate DynamoDB table."""
    table = dynamodb.Table(TABLE_NAME)
    items = [
        {
            "sct_vtcw_reset#sct_vtcw": "0#2025-07-11T12:34:56Z",
            "packet_blob": b"binary_data_string",
        },
        {
            "sct_vtcw_reset#sct_vtcw": "0#2025-07-12T12:34:57Z",
            "packet_blob": b"binary_data_string",
        },
    ]
    for item in items:
        table.put_item(Item=item)

    return item


def test_query_by_sct_vtcw(dynamodb, populate_table):
    """Test to query irregular packet length."""
    table = dynamodb.Table(TABLE_NAME)

    response = table.query(
        KeyConditionExpression=Key("sct_vtcw_reset#sct_vtcw").eq(
            "0#2025-07-12T12:34:57Z"
        )
    )

    items = response["Items"]
    assert items[0]["sct_vtcw_reset#sct_vtcw"] == "0#2025-07-12T12:34:57Z"
