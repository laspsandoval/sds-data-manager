import os
import json
import boto3
import pytest
from moto import mock_dynamodb

# Correct import path for the Lambda function
from sds_data_manager.lambda_code.IAlirtCode.ialirt_ingest import lambda_handler


@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'


@pytest.fixture(scope='function')
def dynamodb_client(aws_credentials):
    with mock_dynamodb():
        yield boto3.client('dynamodb', region_name='us-west-2')


@pytest.fixture(scope='function')
def dynamodb_table(dynamodb_client):
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table_name = 'test_table'
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': 'packet_filename',
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'packet_filename',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 1,
            'WriteCapacityUnits': 1
        }
    )

    # Wait for the table to exist
    table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
    print(f"Table {table_name} created and active.")

    yield table

    # Clean up
    table.delete()
    dynamodb.meta.client.get_waiter('table_not_exists').wait(TableName=table_name)
    print(f"Table {table_name} deleted.")


@pytest.fixture(scope='function')
def set_env_vars():
    os.environ['TABLE_NAME'] = 'test_table'
    yield
    del os.environ['TABLE_NAME']


def test_lambda_handler(dynamodb_table, set_env_vars):
    # Mock event data
    event = {
        "detail": {
            "object": {
                "key": "path/to/s3/object/file.txt"
            }
        }
    }
    context = {}

    # Check that the table exists in the mock environment
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table_name = os.environ['TABLE_NAME']
    table = dynamodb.Table(table_name)

    try:
        table.load()
        print(f"Table {table_name} exists and is active.")
    except Exception as e:
        print(f"Error loading table {table_name}: {e}")
        assert False, f"Table {table_name} should exist but was not found."

    # Call the lambda handler
    lambda_handler(event, context)

    # Check if the item was added to the DynamoDB table
    response = table.get_item(Key={'packet_filename': 'file.txt'})
    item = response.get('Item')

    assert item is not None
    assert item['packet_filename'] == 'file.txt'
    assert item['sct_vtcw_reset#sct_vtcw'] == '0#2025-07-11T12:34:56Z'
    assert item['packet_length'] == 1464
    assert item['packet_blob'] == b'binary_data_string'
    assert item['src_seq_ctr'] == 1
    assert item['irregular_packet'] == 'False'
    assert item['ground_station'] == 'GS001'
    assert item['date'] == '2025_200_123456_001'
