"""Setup items for all test types."""

import os
from datetime import datetime
from typing import Optional

import boto3
import pytest
from moto import mock_dynamodb

from sds_data_manager.lambda_code.SDSCode.database.models import (
    AncillaryFiles,
    ScienceFiles,
)


@pytest.fixture()
def setup_dynamodb():
    """Initialize DynamoDB resource and create table."""
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
    os.environ["INGEST_TABLE"] = "imap-ingest-table"
    os.environ["ALGORITHM_TABLE"] = "imap-algorithm-table"

    with mock_dynamodb():
        # Initialize DynamoDB resource
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")

        ingest_table = dynamodb.create_table(
            TableName=os.environ["INGEST_TABLE"],
            KeySchema=[
                # Partition key
                {"AttributeName": "apid", "KeyType": "HASH"},
                # Sort key
                {"AttributeName": "met", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "apid", "AttributeType": "N"},
                {"AttributeName": "met", "AttributeType": "N"},
                {"AttributeName": "ingest_time", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "ingest_time",
                    "KeySchema": [
                        {"AttributeName": "apid", "KeyType": "HASH"},
                        {"AttributeName": "ingest_time", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        algorithm_table = dynamodb.create_table(
            TableName=os.environ["ALGORITHM_TABLE"],
            KeySchema=[
                # Partition key
                {"AttributeName": "apid", "KeyType": "HASH"},
                # Sort key
                {"AttributeName": "met", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "apid", "AttributeType": "N"},
                {"AttributeName": "met", "AttributeType": "N"},
                {"AttributeName": "insert_time", "AttributeType": "S"},
                {"AttributeName": "product_name", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "insert_time",  # Unique index name
                    "KeySchema": [
                        {"AttributeName": "apid", "KeyType": "HASH"},
                        {"AttributeName": "insert_time", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "product_name",  # Unique index name
                    "KeySchema": [
                        {"AttributeName": "apid", "KeyType": "HASH"},
                        {"AttributeName": "product_name", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield {
            "ingest_table": ingest_table,
            "algorithm_table": algorithm_table,
        }


def create_dependency_api_event(
    source: str,
    data_type: str,
    descriptor="sci",
    dep_type: str = "DOWNSTREAM",
    relationship: str = "HARD",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    version: Optional[str] = None,
    trigger_source: Optional[str] = None,
):
    """Create event dictionaries for tests."""
    event = {
        "queryStringParameters": {
            "dependency_type": dep_type,
            "relationship": relationship,
            "data_source": source,
            "data_type": data_type,
            "descriptor": descriptor,
        }
    }
    optional_params = {
        "start_date": start_date,
        "end_date": end_date,
        "version": version,
        "trigger_source": trigger_source,
    }
    for param, value in optional_params.items():
        if value:
            if isinstance(value, list):
                single_val = value[0]
            else:
                single_val = value
            event["queryStringParameters"][param] = single_val

    return event


def _populate_file_catalog(session):
    """Add records to the ScienceFiles table."""
    # Setup: Add records to the database
    test_records = [
        ScienceFiles(
            file_path="/path/to/imap_ultra_l2_sci_20240101_v001.cdf",
            instrument="ultra",
            data_level="l2",
            descriptor="sci",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/imap_hit_l0_raw_20240101_v001.pkts",
            instrument="hit",
            data_level="l0",
            descriptor="raw",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/imap_swe_l0_raw_20240101_v001.pkts",
            instrument="swe",
            data_level="l0",
            descriptor="raw",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/imap_swe_l1a_sci_20240101_v001.cdf",
            instrument="swe",
            data_level="l1a",
            descriptor="sci",
            start_date=datetime(2024, 1, 1),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        # Add multiple swe l1a records but with different start dates
        ScienceFiles(
            file_path="/path/to/imap_swe_l1a_sci_20240102_v001.cdf",
            instrument="swe",
            data_level="l1a",
            descriptor="sci",
            start_date=datetime(2024, 1, 2),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/imap_swe_l1a_sci_20240103_v001.cdf",
            instrument="swe",
            data_level="l1a",
            descriptor="sci",
            start_date=datetime(2024, 1, 3),
            version="v001",
            extension="pkts",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        # Adding a downstream swe l1b file that depends on the science file above
        ScienceFiles(
            file_path="/path/to/imap_swe_l1b_sci_20240102_v001.cdf",
            instrument="swe",
            data_level="l1b",
            descriptor="sci",
            start_date=datetime(2024, 1, 2),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        # Adding files to test for duplicate job
        ScienceFiles(
            file_path="/path/to/imap_lo_l1a_de_20240101_v001.cdf",
            instrument="lo",
            data_level="l1a",
            descriptor="de",
            start_date=datetime(2010, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        ScienceFiles(
            file_path="/path/to/imap_lo_l1a_sci_20240101_v001.cdf",
            instrument="lo",
            data_level="l1a",
            descriptor="spin",
            start_date=datetime(2010, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        AncillaryFiles(
            file_path="/path/to/imap_swe_l1b-in-flight-cal_20230101_v001.cdf",
            instrument="swe",
            descriptor="l1b-in-flight-cal",
            start_date=datetime(2023, 1, 1),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
        AncillaryFiles(
            file_path="/path/to/imap_swe_l1b-in-flight-cal_20231231_20240102_v002.cdf",
            instrument="swe",
            descriptor="l1b-in-flight-cal",
            start_date=datetime(2023, 12, 31),
            end_date=datetime(2024, 1, 2),
            version="v001",
            extension="cdf",
            ingestion_date=datetime.strptime(
                "2024-01-25 23:35:26+00:00", "%Y-%m-%d %H:%M:%S%z"
            ),
        ),
    ]
    session.add_all(test_records)
    session.commit()
