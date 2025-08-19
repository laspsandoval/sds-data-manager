"""Tests the scheduled job lambda."""

from unittest.mock import call, patch

from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas import (
    batch_starter,
)
from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas.scheduled_job import (
    lambda_handler,
)


@patch(
    "sds_data_manager.lambda_code.SDSCode.pipeline_lambdas.scheduled_job.read_scheduled_job_config"
)
def test_scheduled_processing_event(mock_read_scheduled_job_config, session):
    """Tests ``lambda_handler`` when invoked with a scheduled job event."""
    context = {"context": "sample_context"}

    mock_read_scheduled_job_config.return_value = {
        "cron(20 6 * * ? *)": [
            {
                "data_source": "glows",
                "data_type": "l3b",
                "descriptor": "ion-rate-profile",
            },
        ],
        "cron(22 6 * * ? *)": [
            {
                "data_source": "hi",
                "data_type": "l3",
                "descriptor": "h90-ena-h-sf-sp-full-hae-6deg-3mo",
            },
            {
                "data_source": "lo",
                "data_type": "l3",
                "descriptor": "ilo-ena-h-sf-sp-full-hae-6deg-3mo",
            },
        ],
    }

    with (
        patch.object(batch_starter, "BATCH_CLIENT") as mock_batch_client,
    ):
        lambda_handler({"scheduled": "cron(20 6 * * ? *)"}, context)

        # Verify we submit the glows daily job
        assert mock_batch_client.submit_job.call_count == 1
        mock_batch_client.submit_job.assert_called_with(
            jobName="glows-l3b-ion-rate-profile-job-1",
            jobQueue="ProcessingJobQueue",
            jobDefinition="ProcessingJob-glows-l3",
            containerOverrides={
                "command": [
                    "--instrument",
                    "glows",
                    "--data-level",
                    "l3b",
                    "--descriptor",
                    "ion-rate-profile",
                    "--start-date",
                    "20000101",
                    "--version",
                    "v001",
                    "--dependency",
                    "imap_glows_l3b_ion-rate-profile-4f53cda1_20000101_v001.json",
                    "--upload-to-sdc",
                ]
            },
            retryStrategy=batch_starter.BATCH_JOB_RETRY_STRATEGY,
        )

        mock_batch_client.submit_job.reset_mock()

        lambda_handler({"scheduled": "cron(22 6 * * ? *)"}, context)
        # Verify we submit both sp maps daily jobs
        assert mock_batch_client.submit_job.call_count == 2
        mock_batch_client.submit_job.assert_has_calls(
            [
                call(
                    jobName="hi-l3-h90-ena-h-sf-sp-full-hae-6deg-3mo-job-2",
                    jobQueue="ProcessingJobQueue",
                    jobDefinition="ProcessingJob-hi-l3",
                    containerOverrides={
                        "command": [
                            "--instrument",
                            "hi",
                            "--data-level",
                            "l3",
                            "--descriptor",
                            "h90-ena-h-sf-sp-full-hae-6deg-3mo",
                            "--start-date",
                            "20000101",
                            "--version",
                            "v001",
                            "--dependency",
                            "imap_hi_l3_h90-ena-h-sf-sp-full-hae-6deg-3mo-4f53cda1_20000101_v001.json",
                            "--upload-to-sdc",
                        ]
                    },
                    retryStrategy=batch_starter.BATCH_JOB_RETRY_STRATEGY,
                ),
                call(
                    jobName="lo-l3-ilo-ena-h-sf-sp-full-hae-6deg-3mo-job-3",
                    jobQueue="ProcessingJobQueue",
                    jobDefinition="ProcessingJob-lo-l3",
                    containerOverrides={
                        "command": [
                            "--instrument",
                            "lo",
                            "--data-level",
                            "l3",
                            "--descriptor",
                            "ilo-ena-h-sf-sp-full-hae-6deg-3mo",
                            "--start-date",
                            "20000101",
                            "--version",
                            "v001",
                            "--dependency",
                            "imap_lo_l3_ilo-ena-h-sf-sp-full-hae-6deg-3mo-4f53cda1_20000101_v001.json",
                            "--upload-to-sdc",
                        ]
                    },
                    retryStrategy=batch_starter.BATCH_JOB_RETRY_STRATEGY,
                ),
            ]
        )
