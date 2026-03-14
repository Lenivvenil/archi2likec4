"""Tests for CLI entry point (archi2likec4.pipeline:main)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from archi2likec4.pipeline import main


class TestCLIArgs:
    """Argument parsing and flag handling."""

    def test_default_args(self):
        """Default model_root and output_dir are used when no args given."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline._generate'), \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (0, 0, {}, 0, 0)
            main()
            assert cfg.model_root == Path('architectural_repository/model').resolve()
            assert cfg.output_dir == Path('output')

    def test_strict_flag(self):
        """--strict sets config.strict = True."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline._generate'), \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4', '--strict']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (0, 0, {}, 0, 0)
            main()
            assert cfg.strict is True

    def test_verbose_flag(self):
        """--verbose sets config.verbose = True."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline._generate'), \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4', '--verbose']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (0, 0, {}, 0, 0)
            main()
            assert cfg.verbose is True

    def test_dry_run_exits_zero(self):
        """--dry-run exits with code 0 after validation."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline._generate') as mock_gen, \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4', '--dry-run']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (0, 0, {}, 0, 0)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_gen.assert_not_called()

    def test_custom_paths(self):
        """Custom model_root and output_dir from positional args."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline._generate'), \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4', '/tmp/model', '/tmp/out']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (0, 0, {}, 0, 0)
            main()
            assert cfg.model_root == Path('/tmp/model').resolve()
            assert cfg.output_dir == Path('/tmp/out')


class TestCLIErrorHandling:
    """Exit codes on errors."""

    def test_gate_errors_exit_1(self):
        """Quality-gate errors cause exit 1."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (0, 3, {}, 0, 0)  # 3 errors
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_strict_warnings_exit_1(self):
        """With --strict, warnings cause exit 1."""
        with patch('archi2likec4.pipeline._parse'), \
             patch('archi2likec4.pipeline._build'), \
             patch('archi2likec4.pipeline._validate') as mock_validate, \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4', '--strict']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_validate.return_value = (5, 0, {}, 0, 0)  # 5 warnings, 0 errors
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_config_error_exit_2(self):
        """Config FileNotFoundError causes exit 2."""
        with patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('sys.argv', ['archi2likec4', '--config', 'missing.yaml']):
            mock_load.side_effect = FileNotFoundError('Config file not found: missing.yaml')
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_input_not_found_exit_2(self):
        """FileNotFoundError during parse causes exit 2."""
        with patch('archi2likec4.pipeline._parse') as mock_parse, \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_parse.side_effect = FileNotFoundError('model dir not found')
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_unexpected_error_exit_1(self):
        """Any unexpected error during pipeline causes exit 1."""
        with patch('archi2likec4.pipeline._parse') as mock_parse, \
             patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('sys.argv', ['archi2likec4']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            mock_parse.side_effect = ValueError('bad data')
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_model_root_not_found_exit_2(self):
        """Non-existent model_root causes exit 2."""
        with patch('archi2likec4.pipeline.load_config') as mock_load, \
             patch('sys.argv', ['archi2likec4', '/nonexistent/path']):
            cfg = MagicMock()
            cfg.strict = False
            cfg.verbose = False
            cfg.dry_run = False
            mock_load.return_value = cfg
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2


class TestWebSubcommand:
    """Web subcommand dispatch."""

    def test_web_subcommand_dispatches(self):
        """'web' subcommand calls run_web_cli."""
        with patch('sys.argv', ['archi2likec4', 'web']), \
             patch('archi2likec4.web.run_web_cli') as mock_web:
            main()
            mock_web.assert_called_once()
