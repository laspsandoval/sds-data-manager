"""Stack for creating the IALIRT database."""

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

        Note:
        DynamoDB's table defines the key schema and any secondary indexes.
        The non-key attributes are included items are added to the table.
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
            # Partition key (PK) = spacecraft time ugps.
            partition_key=ddb.Attribute(
                name="sct_vtcw_reset#sct_vtcw",
                type=ddb.AttributeType.STRING,
            ),
            # Enable DynamoDB streams for real-time processing
            stream=ddb.StreamViewType.NEW_IMAGE,
            # Define the read and write capacity units.
            # TODO: change to provisioned capacity mode in production.
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,  # On-Demand capacity mode.
        )
