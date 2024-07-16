"""Configure the indexer lambda stack."""

import pathlib

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python_alpha as lambda_alpha_
from constructs import Construct


class IalirtIngestLambda(Stack):
    """Stack for indexer lambda."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env: cdk.Environment,
        packet_data_table,
        ialirt_bucket,
        **kwargs,
    ) -> None:
        """IndexerLambda Stack.

        Parameters
        ----------
        scope : Construct
            Parent construct.
        construct_id : str
            A unique string identifier for this construct.
        env : obj
            The environment
        packet_data_table : TODO
            The DB secret name
        ialirt_bucket : obj
            The data bucket
        kwargs : dict
            Keyword arguments

        """
        super().__init__(scope, construct_id, env=env, **kwargs)

        lambda_role = iam.Role(
            self, "IalirtIngestLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "s3:GetObject",
                ],
                resources=[packet_data_table.table_arn, f"{ialirt_bucket.bucket_arn}/*"]
            )
        )

        ialirt_ingest_lambda = lambda_alpha_.PythonFunction(
            self,
            id="IalirtIngestLambda",
            function_name="ialirt-ingest",
            entry=str(
                pathlib.Path(__file__).parent.joinpath("..", "lambda_code").resolve()
            ),
            index="IAlirtCode/ingest.py",
            handler="lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            timeout=cdk.Duration.minutes(1),
            memory_size=1000,
            role=lambda_role,
            environment={
                "TABLE_NAME": packet_data_table.table_name,
                "S3_BUCKET": ialirt_bucket.bucket_name,
            },
        )

        packet_data_table.grant_read_write_data(ialirt_ingest_lambda)

        # The resource is deleted when the stack is deleted.
        ialirt_ingest_lambda.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        # Event that triggers Lambda:
        # Arrival of packets in s3 bucket.
        ialirt_data_arrival_rule = events.Rule(
            self,
            "IalirtDataArrival",
            rule_name="ialirt-data-arrival",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [ialirt_bucket.bucket_name]},
                    "object": {"key": [{"prefix": "packets/"}]},
                },
            ),
        )

        # Add the Lambda function as the target for the rules
        ialirt_data_arrival_rule.add_target(targets.LambdaFunction(ialirt_ingest_lambda))
