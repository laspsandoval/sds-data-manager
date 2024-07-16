# Test the IAlirt ingest Lambda function.
import boto3
import pytest
from moto import mock_dynamodb
from sds_data_manager.lambda_code.IAlirtCode.ialirt_ingest import lambda_handler


@pytest.fixture
def dynamodb_table():
    """Fixture to create a mock DynamoDB table."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        table = dynamodb.create_table(
            TableName='imap-packetdata-table',
            KeySchema=[
                {
                    'AttributeName': 'packet_filename',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'sct_vtcw_reset#sct_vtcw',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'packet_filename',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'sct_vtcw_reset#sct_vtcw',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        yield table
        table.delete()


@pytest.fixture
def s3_event():
    """Fixture to create a mock S3 event."""
    return {
        "detail-type": "Object Created",
        "source": "aws.s3",
        "time": "2025-07-11T12:34:56Z",
        "detail": {
            "version": "0",
            "bucket": {"name": "sds-data-123456789012"},
            "object": {
                "key": "imap/hit/l0/2025/07/imap_hit_l0_sci-test_20250711_v001.pkts",
                "reason": "PutObject",
            },
        },
    }


def test_lambda_handler(dynamodb_table, s3_event, monkeypatch):
    """Test the lambda_handler function."""
    # Set environment variable
    monkeypatch.setenv('TABLE_NAME', dynamodb_table.name)

    # Invoke the Lambda function
    response = lambda_handler(s3_event, None)

    # Verify the response
    assert response["statusCode"] == 200

    # Check the DynamoDB table for the new item
    result = dynamodb_table.get_item(Key={
        'packet_filename': 'imap_hit_l0_sci-test_20250711_v001.pkts',
        'sct_vtcw_reset#sct_vtcw': '0#2025-07-11T12:34:56Z'
    })
    item = result.get('Item', None)
    assert item is not None
    assert item['packet_filename'] == 'imap_hit_l0_sci-test_20250711_v001.pkts'
    assert item['sct_vtcw_reset#sct_vtcw'] == '0#2025-07-11T12:34:56Z'
    assert item['packet_length'] == 1464
    assert item['ground_station'] == 'GS001'
    assert item['date'] == '2025_200_123456_001'
    assert item['irregular_packet'] == 'False'
