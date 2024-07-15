"""Configure the IAlirt database stack."""

from aws_cdk import (
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_dynamodb as ddb,
)
from constructs import Construct


class IAlirtDatabaseStack(Stack):
    """Stack for creating database"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Parameters
        ----------
        scope : Construct
            The App object in which to create this Stack
        construct_id : str
            The ID (name) of the stack
        """
        super().__init__(scope, construct_id, **kwargs)

        # Add a DynamoDB table for the metadata
        self.metadata_table = ddb.TableV2(
            self,
            "MetadataTable",
            table_name="imap-packetdata-table",
            removal_policy=RemovalPolicy.DESTROY,  # Change to RemovalPolicy.RETAIN if you want to keep the table
            point_in_time_recovery=True,
            partition_key=ddb.Attribute(
                name="PK",
                type=ddb.AttributeType.STRING,
                # This is the partition key (PK) which is left as a generic string. For our purposes, this is
                # going to be the filename alone without path. This gives uniqueness of files down to the second.
            ),
            sort_key=ddb.Attribute(
                name="SK",
                type=ddb.AttributeType.STRING,
                # This is a sort key (SK) and is a sortable field. For our purposes with vertical partitioning
                # the most common SK is going to be the type of file (e.g. CR, PDS, L1b, etc.). This will be used
                # to query for all files of a certain type using a global secondary index.
            ),
            dynamo_stream=ddb.StreamViewType.NEW_IMAGE,
        )

        # Add a GSI partitioned by creation date (e.g. 2025/12/25) and sorted by
        # the full object creation timestamp (e.g. 2025-12-25T11:22:33)
        # This GSI supports querying and sorting data that appeared during a specific timeframe
        self.metadata_table.add_global_secondary_index(
            index_name="relevant-date-index",
            partition_key=ddb.Attribute(
                name="applicable-date", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="SK", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.INCLUDE,
            non_key_attributes=["first-packet-time", "last-packet-time"],
        )
