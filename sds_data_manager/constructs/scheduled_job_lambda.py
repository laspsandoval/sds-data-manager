"""Module containing constructs for the Schedule Job Lambda Function."""

import aws_cdk as cdk
from aws_cdk import Duration, Environment, aws_events
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secrets
from constructs import Construct

from sds_data_manager.constructs.database_construct import SdpDatabase


class ScheduledJobLambda(Construct):
    """Generic Construct with customizable runtime code."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env: Environment,
        data_bucket: s3.Bucket,
        code: lambda_.Code,
        rds_construct: SdpDatabase,
        rds_security_group: ec2.SecurityGroup,
        vpc: ec2.Vpc,
        layers: list,
        **kwargs,
    ):
        """ScheduledJobLambda Constructor.

        Parameters
        ----------
        scope : Construct
            Parent construct.
        construct_id : str
            A unique string identifier for this construct.
        env : Environment
            Account and region.
        data_bucket: s3.Bucket
            S3 bucket.
        code : lambda_.Code
            Lambda code bundle.
        rds_construct: SdpDatabase
            Database stack.
        rds_security_group : ec2.SecurityGroup
            RDS security group.
        vpc : ec2.Vpc
            VPC into which to put the resources that require networking.
        layers : list
            List of Lambda layers cdk.cdfnOutput names.
        kwargs : dict
            Keyword arguments

        """
        super().__init__(scope, construct_id, **kwargs)

        # Define Lambda Environment Variables
        lambda_environment = {
            "S3_BUCKET": f"{data_bucket.bucket_name}",
            "SECRET_NAME": rds_construct.rds_creds.secret_name,
            "ACCOUNT": f"{env.account}",
            "REGION": f"{env.region}",
        }
        # Lambda should use private subnet
        subnet = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)

        self.scheduled_job_lambda = lambda_.Function(
            self,
            "ScheduledJobLambda",
            function_name="ScheduledJobLambda",
            code=code,
            handler="SDSCode.pipeline_lambdas.scheduled_job.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            environment=lambda_environment,
            memory_size=512,
            timeout=Duration.minutes(1),
            vpc=vpc,
            vpc_subnets=subnet,
            security_groups=[rds_security_group],
            allow_public_subnet=True,
            layers=layers,
        )

        # Permissions to send event to EventBridge
        # and submit batch job
        lambda_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["events:PutEvents", "batch:SubmitJob"],
            resources=[
                "*",
            ],
        )
        self.scheduled_job_lambda.add_to_role_policy(lambda_policy)
        data_bucket.grant_read_write(self.scheduled_job_lambda)
        rds_secret = secrets.Secret.from_secret_name_v2(
            self, "rds_secret", rds_construct.secret_name
        )
        rds_secret.grant_read(grantee=self.scheduled_job_lambda)

        self.scheduled_job_lambda.add_permission(
            "AllowEventBridgeInvokeScheduled",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:events:{env.region}:{env.account}:rule/ProcessingScheduledJob*",
        )

        scheduled_rules = {
            # Example:
            # "glows": "cron(20 6 * * ? *)",
            # "sp_maps": "cron(20 14 * * ? *)",
        }

        for name, schedule_expression in scheduled_rules.items():
            aws_events.CfnRule(
                scope=scope,
                id=f"ProcessingScheduledJob-{name}",
                name=f"ProcessingScheduledJob-{name}",
                description=f"Trigger 'batch starter' scheduled processing job: {name}",
                schedule_expression=schedule_expression,
                state="ENABLED",
                targets=[
                    aws_events.CfnRule.TargetProperty(
                        arn=self.scheduled_job_lambda.function_arn,
                        id=f"{name}",
                        input=cdk.Fn.sub(f'{{"scheduled": "{name}"}}'),
                    )
                ],
            )
