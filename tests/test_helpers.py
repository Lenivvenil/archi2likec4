"""Tests for tests/helpers.py — ensure MockConfig stays in sync with ConvertConfig."""

import dataclasses

from archi2likec4.config import ConvertConfig
from tests.helpers import MockConfig


class TestMockConfigCompleteness:
    """Issue #24: MockConfig must have all ConvertConfig fields."""

    def test_all_config_fields_present(self):
        config_fields = {f.name for f in dataclasses.fields(ConvertConfig)}
        mock = MockConfig()
        mock_attrs = set(vars(mock).keys())
        missing = config_fields - mock_attrs
        assert not missing, f"MockConfig is missing ConvertConfig fields: {missing}"

    def test_deployment_env_default(self):
        mock = MockConfig()
        assert mock.deployment_env == 'prod'

    def test_deployment_env_override(self):
        mock = MockConfig(deployment_env='staging')
        assert mock.deployment_env == 'staging'
