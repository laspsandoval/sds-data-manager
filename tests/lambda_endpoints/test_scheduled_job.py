"""Tests the scheduled job lambda."""

from unittest.mock import call, patch

from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas import (
    batch_starter,
)
from sds_data_manager.lambda_code.SDSCode.pipeline_lambdas.scheduled_job import (
    lambda_handler,
)


def test_scheduled_processing_event(session):
    """Tests ``lambda_handler`` when invoked with a scheduled job event."""
    context = {"context": "sample_context"}

    with (
        patch.object(batch_starter, "BATCH_CLIENT") as mock_batch_client,
    ):
        lambda_handler(
            {
                "scheduled": {
                    "data_source": "glows",
                    "data_type": "l3b",
                    "descriptor": "ion-rate-profile",
                }
            },
            context,
        )
        # Verify the function was called once for the glows daily job
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

        lambda_handler(
            {
                "scheduled": {
                    "data_source": "hi",
                    "data_type": "l3",
                    "descriptor": "h90-ena-h-sf-sp-full-hae-6deg-3mo",
                }
            },
            context,
        )
        # Verify the function was called once for the sp maps daily job
        assert mock_batch_client.submit_job.call_count == 1
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
            ]
        )
