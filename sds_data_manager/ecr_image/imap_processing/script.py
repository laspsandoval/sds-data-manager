#!/usr/bin/env python3
import os

from imap_processing.swe import decom_swe


def batch_job_task():
    # This is a dummpy code that runs in batch job
    instrument = os.environ.get("INSTRUMENT", "SWE")
    if instrument == "SWE":
        pip_path = "/usr/local/lib/python3.11/site-packages"
        data_file = "science_block_20221116_163611Z_idle.bin"
        data_file = f"{pip_path}/imap_processing/swe/tests/{data_file}"
        decom_data = decom_swe.decom_packets(data_file)
        print(decom_data[0].header)
    else:
        print(f"{instrument} not supported yet")

    return "COMPLETE"


if __name__ == "__main__":
    batch_job_task()
