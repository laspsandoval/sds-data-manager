#! /usr/bin/env python3
"""Triggers the api endpoint to reprocess the data."""

# ruff : noqa: S310
import argparse
import contextlib
import logging
import os
import urllib.request
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@contextlib.contextmanager
def _get_url_response(url: str):
    """Get the response from a URL.

    This is a helper function to make it easier to handle
    the different types of errors that can occur when
    opening a URL and write out the response body.

    Parameters
    ----------
    url: str
        The url string to query the api with.

    Yields
    ------
    http.client.HTTPResponse
        The response object received from the API.
    """
    try:
        # Open the URL and yield the response
        req = urllib.request.Request(url, method="POST")
        # Add access token to request
        req.add_header("Authorization", f"Bearer {os.environ.get('GALAXY_API_TOKEN')}")
        with urllib.request.urlopen(req) as response:
            yield response
    except HTTPError as e:
        message = (
            f"HTTP Error: {e.code} - {e.reason}\n"
            f"Server Message: {e.read().decode('utf-8')}"
        )
        raise URLError(message) from e
    except URLError as e:
        message = f"URL Error: {e.reason}"
        raise URLError(message) from e


def trigger_bulk_reprocessing(
    start_date: str,
    end_date: str,
    instrument: Optional[str] = None,
    data_level: Optional[str] = None,
    descriptor: Optional[str] = None,
):
    """Send a POST request to the reprocessing api endpoint.

    Parameters
    ----------
    start_date: str
        Start date in format YYYYMMDD
    end_date: str
        End date in format YYYYMMDD
    instrument: str
        Instrument name
    data_level: str, optional
        Data level
    descriptor: str, optional
        Descriptor for the data product.

    Returns
    -------
    str
        Response from the API
    """
    query_params = {
        "reprocessing": "True",
        "start_date": start_date,
        "end_date": end_date,
    }

    # Add optional parameters if provided
    for param in ["instrument", "data_level", "descriptor"]:
        if locals()[param] is not None:
            query_params[param] = locals()[param]
    base = "https://api.dev.imap-mission.com/auth/reprocess?"
    url = f"{base}{urlencode(query_params)}"

    print(f"Triggering bulk reprocessing for {query_params} with url {url}")
    with _get_url_response(url) as response:
        # Retrieve the response
        response_text = response.read().decode("utf-8")
        if response.status == 200:
            print("Reprocessing triggered successfully.")
        else:
            print(f"Reprocessing triggered with api result: {result}")


if __name__ == "__main__":
    # Parse the CLI command for the input data:
    parser = argparse.ArgumentParser(
        description="Trigger bulk reprocessing of data for a specific time range."
    )
    parser.add_argument(
        "-s",
        "--start_date",
        dest="start_date",
        action="store",
        required=True,
        help="Reprocessing start date in format YYYYMMDD",
    )
    parser.add_argument(
        "-e",
        "--end_date",
        dest="end_date",
        action="store",
        required=True,
        help="Reprocessing end date in format YYYYMMDD",
    )
    parser.add_argument(
        "-i",
        "--instrument",
        dest="instrument",
        default=None,
        action="store",
        help="Instrument name to reprocess",
    )
    parser.add_argument(
        "-l",
        "--data_level",
        dest="data_level",
        action="store",
        default=None,
        help="Data level to reprocess(optional)",
    )
    parser.add_argument(
        "-d",
        "--descriptor",
        dest="descriptor",
        action="store",
        default=None,
        help="Descriptor for the data to reprocess(optional)",
    )

    args = parser.parse_args()

    # Validate date format
    for date in [args.start_date, args.end_date]:
        if len(date) != 8 and not isinstance(date, str):
            parser.error(f"Date {date} must be in format YYYYMMDD")

    result = trigger_bulk_reprocessing(
        args.start_date,
        args.end_date,
        args.instrument,
        args.data_level,
        args.descriptor,
    )
