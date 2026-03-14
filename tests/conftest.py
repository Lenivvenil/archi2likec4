"""Shared test fixtures and mock objects.

Import via: from tests.helpers import MockConfig, MockBuilt
Or use the pytest fixtures below.
"""

import pytest

from tests.helpers import MockBuilt, MockConfig


@pytest.fixture
def mock_config():
    return MockConfig()


@pytest.fixture
def mock_built():
    return MockBuilt()
