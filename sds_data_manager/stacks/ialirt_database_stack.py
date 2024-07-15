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
    """Stack for creating the IALIRT database."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Initialize the IALIRT database stack.

        Parameters
        ----------
        scope : Construct
            The App object in which to create this Stack
        construct_id : str
            The ID (name) of the stack
        **kwargs
            Additional keyword arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.packet_data_table = ddb.Table(
            self,
            "PacketDataTable",
            table_name="imap-packetdata-table",
            # Change to RemovalPolicy.RETAIN to keep the table after stack deletion.
            removal_policy=RemovalPolicy.DESTROY,
            # Restore data to any point in time within the last 35 days.
            point_in_time_recovery=False,
            # Partition key (PK) = filename.
            partition_key=ddb.Attribute(
                name="packet_filename",
                type=ddb.AttributeType.STRING,
            ),
            # Sort key (PK) = reset # + spacecraft time ugps.
            sort_key=ddb.Attribute(
                name="sct_vtcw_reset#sct_vtcw",
                type=ddb.AttributeType.STRING,
            ),
            # Enable DynamoDB streams for real-time processing
            stream=ddb.StreamViewType.NEW_IMAGE,
        )

        # GSI partitioned by packet length and
        # sorted by sct_vtcw_reset#sct_vtcw
        self.packet_data_table.add_global_secondary_index(
            index_name="PacketLengthIndex",
            partition_key=ddb.Attribute(
                name="packet_length", type=ddb.AttributeType.NUMBER
            ),
            sort_key=ddb.Attribute(
                name="sct_vtcw_reset#sct_vtcw", type=ddb.AttributeType.STRING
            ),
            # Specifies what keys to include.
            projection_type=ddb.ProjectionType.INCLUDE,
            non_key_attributes=["packet_filename"],
        )
