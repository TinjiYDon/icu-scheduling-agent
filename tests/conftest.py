"""Keep normal test runs independent of the developer's PostgreSQL database."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-db", action="store_true", default=False,
        help="Run integration tests against the configured local PostgreSQL database.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-db"):
        return
    skip = pytest.mark.skip(reason="requires PostgreSQL; enable explicitly with --run-db")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
