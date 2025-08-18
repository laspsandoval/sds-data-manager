"""Reader for the scheduled job config file."""

from dataclasses import dataclass
from pathlib import Path

from imap_data_access import VALID_DATALEVELS, VALID_INSTRUMENTS

CONFIG_PATH = Path(__file__).parent / "scheduled_jobs_config.csv"


@dataclass
class ScheduledJobInfo:
    """Schedule job dataclass."""

    schedule: str
    instrument: str
    data_level: str
    descriptor: str


def read_scheduled_job_config() -> list[ScheduledJobInfo]:
    """Read the scheduled job config.

    Returns
    -------
    List of ScheduledJobInfo objects from the csv.
    """
    header = [
        "schedule",
        "instrument",
        "data_level",
        "descriptor",
    ]

    scheduled_jobs_info = []

    with open(CONFIG_PATH) as f:
        for line in f:
            if len(line) <= 1 or line.startswith("#"):
                # Skip empty lines and comments
                continue

            contents = [item.strip() for item in line.split(",")]
            if len(contents) != 4:
                raise ValueError(
                    f"Each scheduled job should have {header}\nCurrent line: {line}"
                )
            if contents[1] not in VALID_INSTRUMENTS:
                raise ValueError(f"Invalid instrument: {contents[1]}")
            if contents[2] not in VALID_DATALEVELS:
                raise ValueError(f"Invalid data level: {contents[2]}")

            scheduled_jobs_info.append(ScheduledJobInfo(*contents))
    return scheduled_jobs_info
