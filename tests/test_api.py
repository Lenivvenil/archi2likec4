"""Tests for the public convert() API (archi2likec4.pipeline:convert)."""

from unittest.mock import MagicMock, patch

import pytest

from archi2likec4.exceptions import ConfigError, ParseError, ValidationError
from archi2likec4.pipeline import ConvertResult, convert


def _make_config(*, strict=False, dry_run=False, sync_target=None):
    cfg = MagicMock()
    cfg.strict = strict
    cfg.dry_run = dry_run
    cfg.sync_target = sync_target
    return cfg


class TestConvertReturnsResult:
    """convert() returns ConvertResult on success."""

    def test_convert_returns_result(self, tmp_path):
        """convert() returns a ConvertResult with expected fields."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(1, 0)), \
             patch('archi2likec4.pipeline._generate', return_value=10):
            mock_build.return_value.systems = [MagicMock()] * 3
            mock_build.return_value.integrations = [MagicMock()] * 5
            cfg = _make_config()
            result = convert(tmp_path, tmp_path / 'out', config=cfg)
        assert isinstance(result, ConvertResult)
        assert result.systems_count == 3
        assert result.integrations_count == 5
        assert result.files_written == 10
        assert result.warnings == 1
        assert result.output_dir == tmp_path / 'out'

    def test_convert_dry_run_skips_generate(self, tmp_path):
        """convert() with dry_run=True does not call _generate."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(0, 0)), \
             patch('archi2likec4.pipeline._generate') as mock_gen:
            mock_build.return_value.systems = []
            mock_build.return_value.integrations = []
            cfg = _make_config()
            result = convert(tmp_path, tmp_path / 'out', config=cfg, dry_run=True)
        mock_gen.assert_not_called()
        assert result.files_written == 0

    def test_convert_without_config_calls_load_config(self, tmp_path):
        """When config=None, convert() calls load_config."""
        with patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(0, 0)), \
             patch('archi2likec4.pipeline._generate', return_value=5):
            cfg = _make_config()
            mock_load.return_value = cfg
            mock_build.return_value.systems = []
            mock_build.return_value.integrations = []
            convert(tmp_path, tmp_path / 'out')
        mock_load.assert_called_once()

    def test_convert_does_not_mutate_caller_config(self, tmp_path):
        """convert() must not mutate the ConvertConfig passed by the caller."""
        from archi2likec4.config import load_config
        original_cfg = load_config(None)
        original_model_root = original_cfg.model_root
        original_output_dir = original_cfg.output_dir
        original_dry_run = original_cfg.dry_run

        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(0, 0)), \
             patch('archi2likec4.pipeline._generate', return_value=0):
            mock_build.return_value.systems = []
            mock_build.return_value.integrations = []
            convert(tmp_path, tmp_path / 'out', config=original_cfg, dry_run=True)

        assert original_cfg.model_root == original_model_root
        assert original_cfg.output_dir == original_output_dir
        assert original_cfg.dry_run == original_dry_run


class TestConvertRaisesOnBadInput:
    """convert() raises the right exceptions for bad inputs."""

    def test_convert_raises_on_missing_root(self, tmp_path):
        """FileNotFoundError when model_root does not exist."""
        missing = tmp_path / 'no_such_dir'
        with pytest.raises(FileNotFoundError, match='does not exist'):
            convert(missing, tmp_path / 'out')

    def test_convert_raises_validation_error_on_gate_failure(self, tmp_path):
        """ValidationError when quality gates fail (gate_errors > 0)."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(0, 2)):  # 2 errors
            mock_build.return_value.systems = []
            mock_build.return_value.integrations = []
            cfg = _make_config()
            with pytest.raises(ValidationError, match='Quality gates failed'):
                convert(tmp_path, tmp_path / 'out', config=cfg)

    def test_convert_raises_validation_error_strict_warnings(self, tmp_path):
        """ValidationError when strict=True and gate_warnings > 0."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(3, 0)):  # 3 warnings
            mock_build.return_value.systems = []
            mock_build.return_value.integrations = []
            cfg = _make_config(strict=True)
            with pytest.raises(ValidationError, match='strict mode'):
                convert(tmp_path, tmp_path / 'out', config=cfg)

    def test_convert_raises_config_error(self, tmp_path):
        """ConfigError from load_config propagates to caller."""
        with patch('archi2likec4.pipeline.load_config') as mock_load:
            mock_load.side_effect = ConfigError('bad config')
            with pytest.raises(ConfigError):
                convert(tmp_path, tmp_path / 'out', config_path='bad.yaml')

    def test_convert_raises_parse_error(self, tmp_path):
        """ParseError from _parse propagates to caller."""
        with patch('archi2likec4.pipeline._parse') as mock_parse:
            mock_parse.side_effect = ParseError('all files failed')
            cfg = _make_config()
            with pytest.raises(ParseError):
                convert(tmp_path, tmp_path / 'out', config=cfg)


class TestConvertConfigRuntimeValidation:
    """convert() validates pre-built ConvertConfig at runtime."""

    def test_invalid_deployment_env_raises(self, tmp_path):
        from archi2likec4.config import ConvertConfig
        cfg = ConvertConfig()
        cfg.deployment_env = 'INVALID ID'
        with pytest.raises(ConfigError, match='deployment_env.*invalid C4 identifier'):
            convert(tmp_path, tmp_path / 'out', config=cfg)

    def test_none_deployment_env_raises(self, tmp_path):
        from archi2likec4.config import ConvertConfig
        cfg = ConvertConfig()
        cfg.deployment_env = None  # type: ignore[assignment]
        with pytest.raises(ConfigError, match='deployment_env.*must not be None'):
            convert(tmp_path, tmp_path / 'out', config=cfg)

    def test_invalid_extra_view_pattern_regex_raises(self, tmp_path):
        from archi2likec4.config import ConvertConfig
        cfg = ConvertConfig()
        cfg.extra_view_patterns = [{'pattern': '(', 'view_type': 'functional'}]
        with pytest.raises(ConfigError, match='extra_view_patterns.*invalid regex'):
            convert(tmp_path, tmp_path / 'out', config=cfg)

    def test_invalid_extra_view_pattern_type_raises(self, tmp_path):
        from archi2likec4.config import ConvertConfig
        cfg = ConvertConfig()
        cfg.extra_view_patterns = [{'pattern': '.*', 'view_type': 'bad'}]
        with pytest.raises(ConfigError, match="extra_view_patterns.*must be"):
            convert(tmp_path, tmp_path / 'out', config=cfg)

    def test_valid_prebuilt_config_passes(self, tmp_path):
        from archi2likec4.config import ConvertConfig
        cfg = ConvertConfig()
        cfg.deployment_env = 'prod'
        cfg.extra_view_patterns = [{'pattern': '.*test.*', 'view_type': 'functional'}]
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build') as mock_build, \
             patch('archi2likec4.pipeline._validate', return_value=(0, 0)), \
             patch('archi2likec4.pipeline._generate', return_value=0):
            mock_build.return_value.systems = []
            mock_build.return_value.integrations = []
            result = convert(tmp_path, tmp_path / 'out', config=cfg)
        assert isinstance(result, ConvertResult)
