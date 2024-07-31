"""Setup items for all test types."""

import os

import boto3
import pytest
from moto import mock_dynamodb


@pytest.fixture()
def table():
    """Initialize DynamoDB resource and create table."""
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
    os.environ["TABLE_NAME"] = "imap-data-table"

    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.create_table(
            TableName="imap-data-table",
            KeySchema=[
                # Partition key
                {"AttributeName": "reset_number#met", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "reset_number#met", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table
        table.delete()
