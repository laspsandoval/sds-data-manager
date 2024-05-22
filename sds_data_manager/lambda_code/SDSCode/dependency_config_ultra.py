"""Stores the downstream dependency configuration of Ultra.

This is used to populate pre-processing dependency table in the database.

NOTE: This setup assumes that we get one data file everyday with all
the data of multiple apid. This is why we have only one file for each
l0 and descriptor is raw. And l1a that depends on l0 has 'all' as
descriptor with assumption that l1a could produce multiple files
with different descriptor. Those different descriptor are handle in its own
code in imap_processing repo.
"""

from .database.models import PreProcessingDependency

downstream_dependents = [
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="45events",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="45phxtof",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="45aux",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="45rates",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="90events",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="90phxtof",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="90aux",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l0",
        primary_descriptor="raw",
        dependent_instrument="ultra",
        dependent_data_level="l1a",
        dependent_descriptor="90rates",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
]

# UPSTREAM DEPENDENCIES
upstream_dependents = [
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="45events",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="45phxtof",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="45aux",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="45rates",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="90events",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="90phxtof",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="90aux",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
    PreProcessingDependency(
        primary_instrument="ultra",
        primary_data_level="l1a",
        primary_descriptor="90rates",
        dependent_instrument="ultra",
        dependent_data_level="l0",
        dependent_descriptor="raw",
        relationship="HARD",
        direction="DOWNSTREAM",
    ),
]