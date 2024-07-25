"""Setup items for the infrastructure tests."""

from pathlib import Path

import boto3
import pytest
from aws_cdk import App, Environment
from moto import mock_dynamodb

from sds_data_manager.stacks.lambda_layer_stack import LambdaLayerStack


@pytest.fixture(scope="module")
def account():
    """Set the account number to test with."""
    return "1234567890"


@pytest.fixture(scope="module")
def region():
    """Set the region to test with."""
    return "us-east-1"


@pytest.fixture(scope="module")
def env(account, region):
    """Set the environment to test with."""
    return Environment(account=account, region=region)


@pytest.fixture(scope="module")
def app():
    """Return the app to test with."""
    return App()


@pytest.fixture(scope="module")
def lambda_layer_stack(app, env):
    """Return the lambda layer stack."""
    lambda_code_directory = (
        Path(__file__).parent.parent.parent / "lambda_layer/python"
    ).resolve()
    db_layer_name = "DatabaseDependencies"
    LambdaLayerStack(
        scope=app, id=db_layer_name, layer_dependencies_dir=str(lambda_code_directory)
    )
    return db_layer_name


@pytest.fixture()
def table():
    """Initialize DynamoDB resource and create table."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.create_table(
            TableName="imap-data-table",
            KeySchema=[
                # Partition key
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "sct_vtcw_reset#sct_vtcw", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table
        table.delete()
