import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_dynamodb

TABLE_NAME = "imap-packetdata-table"


@pytest.fixture()
def dynamodb():
    with mock_dynamodb():
        # Initialize DynamoDB resource and create table
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "packet_filename", "KeyType": "HASH"},
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "packet_filename", "AttributeType": "S"},
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "AttributeType": "S"},
                {"AttributeName": "unexpected_length", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "IrregularIndex",
                    "KeySchema": [
                        {"AttributeName": "unexpected_length", "KeyType": "HASH"},
                        {
                            "AttributeName": "sct_vtcw_reset#sct_vtcw",
                            "KeyType": "RANGE",
                        },
                    ],
                    "Projection": {
                        "ProjectionType": "INCLUDE",
                        "NonKeyAttributes": ["packet_filename", "packet_length"],
                    },
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                },
                {
                    "IndexName": "FilenameIndex",
                    "KeySchema": [
                        {"AttributeName": "unexpected_length", "KeyType": "HASH"},
                        {"AttributeName": "packet_filename", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                },
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        yield dynamodb
        table.delete()


@pytest.fixture()
def populate_table(dynamodb):
    table = dynamodb.Table(TABLE_NAME)
    items = [
        {
            "packet_filename": "GS001_2025_200_123456_001.pkts",
            "sct_vtcw_reset#sct_vtcw": "0#2025-07-11T12:34:56Z",
            "packet_length": 1464,
            "packet_blob": b"binary_data_string",
            "src_seq_ctr": 1,
            "unexpected_length": "False",
        },
        {
            "packet_filename": "GS002_2025_201_123457_001.pkts",
            "sct_vtcw_reset#sct_vtcw": "0#2025-07-12T12:34:57Z",
            "packet_length": 1500,
            "packet_blob": b"binary_data_string",
            "src_seq_ctr": 2,
            "unexpected_length": "True",
        },
    ]
    for item in items:
        table.put_item(Item=item)


def test_query_by_irregular_packet_lengths(dynamodb, populate_table):
    table = dynamodb.Table(TABLE_NAME)

    # Querying the IrregularIndex GSI for irregular packets
    response = table.query(
        IndexName="IrregularIndex",
        KeyConditionExpression=Key("unexpected_length").eq("True"),
    )

    items = response["Items"]
    assert items[0]["packet_length"] == 1500
    assert items[0]["packet_filename"] == "GS002_2025_201_123457_001.pkts"
    assert items[0]["sct_vtcw_reset#sct_vtcw"] == "0#2025-07-12T12:34:57Z"


def test_query_by_ground_station_and_date(dynamodb, populate_table):
    table = dynamodb.Table(TABLE_NAME)
    response = table.query(
        IndexName="FilenameIndex",
        KeyConditionExpression=Key('unexpected_length').eq('False') &
                               Key("packet_filename").begins_with("GS001_2025_200"),
    )
    items = response["Items"]
    assert items[0]["packet_filename"] == "GS001_2025_200_123456_001.pkts"


def test_query_by_sct_vtcw_range(dynamodb, populate_table):
    table = dynamodb.Table(TABLE_NAME)

    response = table.query(
        IndexName="IrregularIndex",
        KeyConditionExpression=Key("unexpected_length").eq("True")
        & Key("sct_vtcw_reset#sct_vtcw").between(
            "0#2025-07-11T00:00:00Z", "0#2025-07-13T23:59:59Z"
        ),
    )

    items = response["Items"]
    assert items[0]["packet_filename"] == "GS002_2025_201_123457_001.pkts"
    assert items[0]["packet_length"] == 1500  # Ensure packet_length is included
