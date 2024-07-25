"""Test the IAlirt database stack."""

import pytest
from boto3.dynamodb.conditions import Key


@pytest.fixture()
def populate_table(table):
    """Populate DynamoDB table."""
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


def test_query_by_sct_vtcw(table, populate_table):
    """Test to query irregular packet length."""
    response = table.query(
        KeyConditionExpression=Key("sct_vtcw_reset#sct_vtcw").eq(
            "0#2025-07-12T12:34:57Z"
        )
    )

    items = response["Items"]
    assert items[0]["sct_vtcw_reset#sct_vtcw"] == "0#2025-07-12T12:34:57Z"
