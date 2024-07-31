"""Test the IAlirt database stack."""

import pytest
from boto3.dynamodb.conditions import Key


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


def test_query_by_sct_vtcw(table, populate_table):
    """Test to query irregular packet length."""
    response = table.query(KeyConditionExpression=Key("reset_number#met").eq("0#124"))

    items = response["Items"]
    assert items[0]["reset_number#met"] == "0#124"