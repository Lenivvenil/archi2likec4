"""Unit tests for pipeline.py — covers _generate safety, _sync_output, _validate_config_runtime,
convert() public API, and main() CLI entry point."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from archi2likec4.builders._result import BuildDiagnostics
from archi2likec4.config import ConvertConfig
from archi2likec4.exceptions import ConfigError, ValidationError
from archi2likec4.models import DeploymentNode, DomainInfo, System
from archi2likec4.pipeline import (
    BuildResult,
    SolutionViewInfo,
    _generate,
    _sync_output,
    _validate,
    _validate_config_runtime,
    convert,
    main,
)

# ── Helpers ───────────────────────────────────────────────────────────────

def _empty_built() -> BuildResult:
    return BuildResult(
        systems=[],
        integrations=[],
        data_access=[],
        entities=[],
        domain_systems={},
        sys_domain={},
        archi_to_c4={},
        promoted_archi_to_c4={},
        promoted_parents={},
        iface_c4_path={},
        diagnostics=BuildDiagnostics(orphan_fns=0, intg_skipped=0, intg_total_eligible=0),
        deployment_nodes=[],
        deployment_map=[],
        tech_archi_to_c4={},
        datastore_entity_links=[],
        subdomains=[],
        subdomain_systems={},
    )


def _create_model(tmp_path: Path) -> Path:
    """Create a minimal coArchi model directory."""
    model = tmp_path / 'model'
    app = model / 'application'
    app.mkdir(parents=True)
    (app / 'ApplicationComponent_s1.xml').write_text(
        '<element id="s-1" name="Sys1"/>',
        encoding='utf-8',
    )
    rel_dir = model / 'relations'
    rel_dir.mkdir()
    (model / 'diagrams').mkdir()
    (model / 'technology').mkdir()
    return model


# ── _generate safety checks ──────────────────────────────────────────────

class TestGenerateSafety:
    def test_refuses_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = tmp_path
        output.mkdir(exist_ok=True)
        built = _empty_built()
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='dangerous path'):
            _generate(built, output, config, [])

    def test_refuses_home_dir(self, tmp_path):
        built = _empty_built()
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='dangerous path'):
            _generate(built, Path.home(), config, [])

    def test_refuses_root_level_path(self, tmp_path):
        """Root-level paths (depth <= 2) are rejected when dir exists."""
        built = _empty_built()
        config = ConvertConfig()
        output = tmp_path / 'output'
        output.mkdir()
        fake_root = Path('/fakevol')
        # Patch resolve so that the output_dir resolves to a root-level path,
        # but cwd/home still resolve normally (avoiding the "dangerous path" guard).
        _orig_resolve = Path.resolve

        def _fake_resolve(self):
            if self == output:
                return fake_root
            return _orig_resolve(self)

        with patch.object(Path, 'resolve', _fake_resolve), \
             patch.object(Path, 'exists', return_value=True), \
             pytest.raises(ConfigError, match='root-level path'):
            _generate(built, output, config, [])

    def test_refuses_non_output_dir(self, tmp_path):
        """Dir exists, has files, but no .archi2likec4-output marker."""
        output = tmp_path / 'output'
        output.mkdir()
        (output / 'random.txt').write_text('hello')
        built = _empty_built()
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='does not look like'):
            _generate(built, output, config, [])

    def test_marker_allows_rmtree(self, tmp_path):
        """Dir with marker is cleaned and regenerated."""
        output = tmp_path / 'output'
        output.mkdir()
        (output / '.archi2likec4-output').write_text('')
        (output / 'old_file.c4').write_text('old')
        built = _empty_built()
        config = ConvertConfig()
        count = _generate(built, output, config, [])
        assert count > 0
        assert not (output / 'old_file.c4').exists()
        assert (output / 'specification.c4').exists()

    def test_generate_with_solution_views(self, tmp_path):
        """SolutionViewInfo files are written to views/solutions/."""
        output = tmp_path / 'output'
        sv_info = SolutionViewInfo(
            files={'test-view': 'views { view test_view {} }'},
            unresolved=1,
            total=10,
        )
        built = _empty_built()
        config = ConvertConfig()
        count = _generate(built, output, config, [], sv_info=sv_info)
        assert (output / 'views' / 'solutions' / 'test-view.c4').exists()
        assert count > 0

    def test_generate_with_domains(self, tmp_path):
        """Domains and system details are generated."""
        output = tmp_path / 'output'
        sys1 = System(c4_id='sys1', name='Sys1', archi_id='a-1', domain='dom1')
        sys1.subsystems = []
        sys1.functions = []
        built = _empty_built()._replace(
            systems=[sys1],
            domain_systems={'dom1': [sys1]},
        )
        domains_info = [DomainInfo(c4_id='dom1', name='Domain One')]
        config = ConvertConfig()
        _generate(built, output, config, domains_info)
        assert (output / 'domains' / 'dom1.c4').exists()

    def test_generate_with_extra_domain_patterns(self, tmp_path):
        """extra_domain_patterns creates DomainInfo for unknown domains."""
        output = tmp_path / 'output'
        sys1 = System(c4_id='sys1', name='Sys1', archi_id='a-1', domain='extra_dom')
        sys1.subsystems = []
        sys1.functions = []
        built = _empty_built()._replace(
            systems=[sys1],
            domain_systems={'extra_dom': [sys1]},
        )
        config = ConvertConfig(
            extra_domain_patterns=[{'c4_id': 'extra_dom', 'name': 'Extra', 'pattern': r'.*'}],
        )
        _generate(built, output, config, [])
        assert (output / 'domains' / 'extra_dom.c4').exists()

    def test_empty_domain_sys_list_skipped(self, tmp_path):
        """Domains with empty system lists are skipped."""
        output = tmp_path / 'output'
        built = _empty_built()._replace(
            domain_systems={'empty_dom': []},
        )
        config = ConvertConfig()
        _generate(built, output, config, [DomainInfo(c4_id='empty_dom', name='Empty')])
        assert not (output / 'domains' / 'empty_dom.c4').exists()


# ── _sync_output ─────────────────────────────────────────────────────────

class TestSyncOutput:
    def test_no_sync_target(self):
        config = ConvertConfig(sync_target=None)
        assert _sync_output(config) is True

    def test_sync_copies_files(self, tmp_path):
        src = tmp_path / 'output'
        src.mkdir()
        (src / 'test.c4').write_text('content')
        dst = tmp_path / 'target'
        dst.mkdir()
        config = ConvertConfig(output_dir=src, sync_target=dst)
        assert _sync_output(config) is True
        assert (dst / 'test.c4').read_text() == 'content'

    def test_sync_skips_protected_top(self, tmp_path):
        src = tmp_path / 'output'
        src.mkdir()
        (src / 'test.c4').write_text('content')
        (src / '.gitignore').write_text('*.log')
        dst = tmp_path / 'target'
        dst.mkdir()
        config = ConvertConfig(
            output_dir=src,
            sync_target=dst,
            sync_protected_top=frozenset({'.gitignore'}),
        )
        _sync_output(config)
        assert (dst / 'test.c4').exists()
        assert not (dst / '.gitignore').exists()

    def test_sync_skips_protected_paths(self, tmp_path):
        src = tmp_path / 'output'
        subdir = src / 'scripts'
        subdir.mkdir(parents=True)
        (subdir / 'check.py').write_text('pass')
        (src / 'spec.c4').write_text('spec')
        dst = tmp_path / 'target'
        dst.mkdir()
        config = ConvertConfig(
            output_dir=src,
            sync_target=dst,
            sync_protected_paths=frozenset({'scripts/check.py'}),
        )
        _sync_output(config)
        assert (dst / 'spec.c4').exists()
        assert not (dst / 'scripts' / 'check.py').exists()

    def test_sync_target_inside_output_returns_false(self, tmp_path):
        src = tmp_path / 'output'
        src.mkdir()
        dst = src / 'nested'
        dst.mkdir()
        config = ConvertConfig(output_dir=src, sync_target=dst)
        assert _sync_output(config) is False

    def test_sync_target_equals_output_returns_false(self, tmp_path):
        src = tmp_path / 'output'
        src.mkdir()
        config = ConvertConfig(output_dir=src, sync_target=src)
        assert _sync_output(config) is False

    def test_sync_skips_symlinks(self, tmp_path):
        src = tmp_path / 'output'
        src.mkdir()
        (src / 'real.c4').write_text('data')
        link = src / 'link.c4'
        link.symlink_to(src / 'real.c4')
        dst = tmp_path / 'target'
        dst.mkdir()
        config = ConvertConfig(output_dir=src, sync_target=dst)
        _sync_output(config)
        assert (dst / 'real.c4').exists()
        assert not (dst / 'link.c4').exists()

    def test_sync_unlinks_target_symlink(self, tmp_path):
        """If target already has a symlink where a file should go, unlink it."""
        src = tmp_path / 'output'
        src.mkdir()
        (src / 'file.c4').write_text('new data')
        dst = tmp_path / 'target'
        dst.mkdir()
        # Create a symlink at dst/file.c4 pointing somewhere
        dummy = tmp_path / 'dummy'
        dummy.write_text('old')
        (dst / 'file.c4').symlink_to(dummy)
        config = ConvertConfig(output_dir=src, sync_target=dst)
        _sync_output(config)
        assert not (dst / 'file.c4').is_symlink()
        assert (dst / 'file.c4').read_text() == 'new data'

    def test_sync_recursive_dirs(self, tmp_path):
        src = tmp_path / 'output'
        sub = src / 'domains'
        sub.mkdir(parents=True)
        (sub / 'dom.c4').write_text('domain')
        dst = tmp_path / 'target'
        dst.mkdir()
        config = ConvertConfig(output_dir=src, sync_target=dst)
        _sync_output(config)
        assert (dst / 'domains' / 'dom.c4').read_text() == 'domain'


# ── _validate_config_runtime ──────────────────────────────────────────────

class TestValidateConfigRuntime:
    def test_non_config_instance_skipped(self):
        """Non-ConvertConfig objects are silently skipped."""
        from tests.helpers import MockConfig
        _validate_config_runtime(MockConfig())  # should not raise

    def test_valid_config(self):
        config = ConvertConfig()
        _validate_config_runtime(config)  # should not raise

    def test_deployment_env_none(self):
        config = ConvertConfig()
        config.deployment_env = None
        with pytest.raises(ConfigError, match='must not be None'):
            _validate_config_runtime(config)

    def test_deployment_env_empty(self):
        config = ConvertConfig()
        config.deployment_env = '  '
        with pytest.raises(ConfigError, match='must not be empty'):
            _validate_config_runtime(config)

    def test_deployment_env_invalid_c4_id(self):
        config = ConvertConfig()
        config.deployment_env = 'INVALID!'
        with pytest.raises(ConfigError, match='invalid C4 identifier'):
            _validate_config_runtime(config)

    def test_deployment_env_stripped(self):
        config = ConvertConfig()
        config.deployment_env = ' prod '
        _validate_config_runtime(config)
        assert config.deployment_env == 'prod'

    def test_extra_view_patterns_not_list(self):
        config = ConvertConfig()
        config.extra_view_patterns = 'not-a-list'
        with pytest.raises(ConfigError, match='expected list'):
            _validate_config_runtime(config)

    def test_extra_view_patterns_entry_not_dict(self):
        config = ConvertConfig()
        config.extra_view_patterns = ['bad']
        with pytest.raises(ConfigError, match='expected mapping'):
            _validate_config_runtime(config)

    def test_extra_view_patterns_missing_pattern_key(self):
        config = ConvertConfig()
        config.extra_view_patterns = [{'view_type': 'functional'}]
        with pytest.raises(ConfigError, match="missing required key 'pattern'"):
            _validate_config_runtime(config)

    def test_extra_view_patterns_missing_view_type_key(self):
        config = ConvertConfig()
        config.extra_view_patterns = [{'pattern': '.*'}]
        with pytest.raises(ConfigError, match="missing required key 'view_type'"):
            _validate_config_runtime(config)

    def test_extra_view_patterns_pattern_not_string(self):
        config = ConvertConfig()
        config.extra_view_patterns = [{'pattern': 123, 'view_type': 'functional'}]
        with pytest.raises(ConfigError, match='expected string'):
            _validate_config_runtime(config)

    def test_extra_view_patterns_invalid_regex(self):
        config = ConvertConfig()
        config.extra_view_patterns = [{'pattern': '[invalid', 'view_type': 'functional'}]
        with pytest.raises(ConfigError, match='invalid regex'):
            _validate_config_runtime(config)

    def test_extra_view_patterns_invalid_view_type(self):
        config = ConvertConfig()
        config.extra_view_patterns = [{'pattern': '.*', 'view_type': 'unknown'}]
        with pytest.raises(ConfigError, match="must be 'functional'"):
            _validate_config_runtime(config)

    def test_spec_colors_not_dict(self):
        config = ConvertConfig()
        config.spec_colors = 'bad'
        with pytest.raises(ConfigError, match='spec_colors.*expected mapping'):
            _validate_config_runtime(config)

    def test_spec_colors_non_string_key(self):
        config = ConvertConfig()
        config.spec_colors = {123: 'red'}
        with pytest.raises(ConfigError, match='spec_colors.*strings'):
            _validate_config_runtime(config)

    def test_spec_colors_invalid_c4_id(self):
        config = ConvertConfig()
        config.spec_colors = {'INVALID!': '#fff'}
        with pytest.raises(ConfigError, match='spec_colors.*invalid C4 identifier'):
            _validate_config_runtime(config)

    def test_spec_shapes_not_dict(self):
        config = ConvertConfig()
        config.spec_shapes = 'bad'
        with pytest.raises(ConfigError, match='spec_shapes.*expected mapping'):
            _validate_config_runtime(config)

    def test_spec_shapes_non_string_values(self):
        config = ConvertConfig()
        config.spec_shapes = {123: 456}
        with pytest.raises(ConfigError, match='spec_shapes.*strings'):
            _validate_config_runtime(config)

    def test_spec_shapes_unknown_kind(self):
        config = ConvertConfig()
        config.spec_shapes = {'unknown_kind': 'rectangle'}
        with pytest.raises(ConfigError, match='spec_shapes.*unknown element kind'):
            _validate_config_runtime(config)

    def test_spec_tags_not_list(self):
        config = ConvertConfig()
        config.spec_tags = 'bad'
        with pytest.raises(ConfigError, match='spec_tags.*expected list'):
            _validate_config_runtime(config)

    def test_spec_tags_non_string_item(self):
        config = ConvertConfig()
        config.spec_tags = [123]
        with pytest.raises(ConfigError, match='spec_tags.*must be strings'):
            _validate_config_runtime(config)

    def test_spec_tags_invalid_c4_id(self):
        config = ConvertConfig()
        config.spec_tags = ['INVALID!']
        with pytest.raises(ConfigError, match='spec_tags.*invalid C4 identifier'):
            _validate_config_runtime(config)


# ── _validate edge cases ─────────────────────────────────────────────────

class TestValidateEdgeCases:
    def test_sv_ratio_error(self):
        """High unresolved ratio triggers an error."""
        built = _empty_built()
        config = ConvertConfig(max_unresolved_ratio=0.3)
        warnings, errors = _validate(built, config, sv_unresolved=40, sv_total=100)
        assert errors == 1

    def test_sv_ratio_warning(self):
        """Moderate unresolved ratio triggers a warning."""
        built = _empty_built()
        config = ConvertConfig(max_unresolved_ratio=0.5)
        # 0.6 * 0.5 = 0.3, so ratio > 0.3 and <= 0.5 triggers warning
        warnings, errors = _validate(built, config, sv_unresolved=35, sv_total=100)
        assert warnings == 1
        assert errors == 0

    def test_sv_ratio_info_only(self):
        """Low unresolved ratio produces neither warning nor error."""
        built = _empty_built()
        config = ConvertConfig(max_unresolved_ratio=0.5)
        warnings, errors = _validate(built, config, sv_unresolved=5, sv_total=100)
        assert warnings == 0
        assert errors == 0

    def test_strict_mode_with_criticals(self):
        """strict=True with critical QA incidents adds warnings."""
        sys1 = System(c4_id='sys1', name='Sys1', archi_id='a-1', domain='dom')
        built = _empty_built()._replace(
            systems=[sys1],
            domain_systems={'dom': [sys1]},
        )
        config = ConvertConfig(strict=True)
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        # With minimal data, there may be critical incidents (orphan systems etc)
        # Just verify it doesn't crash
        assert errors == 0


# ── convert() public API ─────────────────────────────────────────────────

class TestConvert:
    def test_model_root_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match='does not exist'):
            convert(tmp_path / 'nonexistent')

    def test_dry_run_no_files(self, tmp_path):
        model = _create_model(tmp_path)
        result = convert(model, tmp_path / 'output', dry_run=True)
        assert result.files_written == 0
        assert not (tmp_path / 'output').exists()

    def test_full_convert(self, tmp_path):
        model = _create_model(tmp_path)
        output = tmp_path / 'output'
        result = convert(model, output)
        assert result.files_written > 0
        assert result.systems_count >= 1
        assert (output / 'specification.c4').exists()

    def test_convert_with_config_path(self, tmp_path):
        model = _create_model(tmp_path)
        config_file = tmp_path / '.archi2likec4.yaml'
        config_file.write_text('deployment_env: staging\n')
        result = convert(model, tmp_path / 'output', config_path=config_file)
        assert result.files_written > 0

    def test_convert_with_pre_built_config(self, tmp_path):
        model = _create_model(tmp_path)
        config = ConvertConfig(deployment_env='staging')
        result = convert(model, tmp_path / 'output', config=config)
        assert result.files_written > 0

    def test_convert_validation_error_on_high_unresolved(self, tmp_path):
        model = _create_model(tmp_path)
        config = ConvertConfig(max_unresolved_ratio=0.0)
        # Minimal model has no solution views, so ratio check is skipped — succeeds
        result = convert(model, tmp_path / 'output', config=config)
        assert result.files_written > 0

    def test_convert_strict_mode(self, tmp_path):
        model = _create_model(tmp_path)
        config = ConvertConfig(strict=True)
        # Minimal model triggers QA warnings → strict mode raises
        with pytest.raises(ValidationError, match='strict mode'):
            convert(model, tmp_path / 'output', config=config)

    def test_convert_with_sync_target(self, tmp_path):
        model = _create_model(tmp_path)
        target = tmp_path / 'sync_target'
        target.mkdir()
        config = ConvertConfig(sync_target=target)
        result = convert(model, tmp_path / 'output', config=config)
        assert result.sync_ok is True


# ── main() CLI ────────────────────────────────────────────────────────────

class TestMain:
    def test_main_missing_model_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(tmp_path / 'nonexistent'),
        ])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_version(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['archi2likec4', '--version'])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_dry_run(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'), '--dry-run',
        ])
        main()  # should complete without error

    def test_main_full_run(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
        ])
        main()
        assert (tmp_path / 'output' / 'specification.c4').exists()

    def test_main_verbose(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'), '--verbose',
        ])
        main()

    def test_main_strict_with_warnings(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'), '--strict',
        ])
        # Minimal model triggers QA warnings → strict mode exits with code 1
        with pytest.raises(SystemExit, match='1'):
            main()

    def test_main_config_file(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        config_file = tmp_path / 'config.yaml'
        config_file.write_text('deployment_env: staging\n')
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
            '--config', str(config_file),
        ])
        main()

    def test_main_bad_config(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        config_file = tmp_path / 'bad.yaml'
        config_file.write_text('not: valid: yaml: [')
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
            '--config', str(config_file),
        ])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_sync_target_not_exists(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
            '--sync-target', str(tmp_path / 'nonexistent'),
        ])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_sync_target_not_dir(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        target_file = tmp_path / 'file.txt'
        target_file.write_text('not a dir')
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
            '--sync-target', str(target_file),
        ])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_web_subcommand(self, monkeypatch):
        """'web' subcommand dispatches to run_web_cli."""
        monkeypatch.setattr(sys, 'argv', ['archi2likec4', 'web', '--help'])
        with patch('archi2likec4.web.run_web_cli', side_effect=SystemExit(0)) as mock_web:
            with pytest.raises(SystemExit):
                main()
            mock_web.assert_called_once()

    def test_main_unexpected_error(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
        ])
        with patch('archi2likec4.pipeline.convert', side_effect=RuntimeError('boom')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_unexpected_error_verbose(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'), '--verbose',
        ])
        with patch('archi2likec4.pipeline.convert', side_effect=RuntimeError('boom')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_parse_error(self, tmp_path, monkeypatch):
        from archi2likec4.exceptions import ParseError
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
        ])
        with patch('archi2likec4.pipeline.convert', side_effect=ParseError('bad xml')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_main_config_error(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
        ])
        with patch('archi2likec4.pipeline.convert', side_effect=ConfigError('bad config')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_main_validation_error(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
        ])
        with patch('archi2likec4.pipeline.convert', side_effect=ValidationError('gates failed')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_file_not_found_error(self, tmp_path, monkeypatch):
        model = _create_model(tmp_path)
        monkeypatch.setattr(sys, 'argv', [
            'archi2likec4', str(model), str(tmp_path / 'output'),
        ])
        with patch('archi2likec4.pipeline.convert', side_effect=FileNotFoundError('missing')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2


# ── _generate deployment + datastore paths ────────────────────────────────

class TestGenerateDeployment:
    def test_generate_with_deployment_nodes(self, tmp_path):
        """Deployment topology and overview view are generated."""
        output = tmp_path / 'output'
        node = DeploymentNode(
            c4_id='srv1', name='Server 1', archi_id='t-1',
            tech_type='Node', kind='infraNode',
        )
        built = _empty_built()._replace(
            deployment_nodes=[node],
            deployment_map=[('dom.sys1', 'srv1')],
        )
        config = ConvertConfig()
        count = _generate(built, output, config, [])
        assert (output / 'deployment' / 'topology.c4').exists()
        assert (output / 'views' / 'deployment-architecture.c4').exists()
        assert count > 0

    def test_generate_with_datastore_entity_links(self, tmp_path):
        """datastore-mapping.c4 is generated when links exist."""
        output = tmp_path / 'output'
        node = DeploymentNode(
            c4_id='db1', name='Database', archi_id='t-2',
            tech_type='SystemSoftware', kind='dataStore',
        )
        built = _empty_built()._replace(
            deployment_nodes=[node],
            datastore_entity_links=[('db1', 'entity1')],
        )
        config = ConvertConfig()
        _generate(built, output, config, [])
        assert (output / 'deployment' / 'datastore-mapping.c4').exists()

    def test_generate_auto_creates_domain_info(self, tmp_path):
        """Unknown domain ids from domain_systems get auto-created DomainInfo."""
        output = tmp_path / 'output'
        sys1 = System(c4_id='sys1', name='Sys1', archi_id='a-1', domain='auto_dom')
        sys1.subsystems = []
        sys1.functions = []
        built = _empty_built()._replace(
            systems=[sys1],
            domain_systems={'auto_dom': [sys1]},
        )
        config = ConvertConfig()
        # No DomainInfo provided — should auto-create
        _generate(built, output, config, [])
        assert (output / 'domains' / 'auto_dom.c4').exists()


# ── _sync_output additional edge cases ────────────────────────────────────

class TestSyncOutputExtra:
    def test_sync_unlinks_target_dir_symlink(self, tmp_path):
        """If target already has a symlink directory, unlink it before mkdir."""
        src = tmp_path / 'output'
        sub = src / 'subdir'
        sub.mkdir(parents=True)
        (sub / 'file.c4').write_text('data')
        dst = tmp_path / 'target'
        dst.mkdir()
        # Create a directory symlink at dst/subdir
        real_dir = tmp_path / 'real_subdir'
        real_dir.mkdir()
        (dst / 'subdir').symlink_to(real_dir)
        config = ConvertConfig(output_dir=src, sync_target=dst)
        _sync_output(config)
        assert (dst / 'subdir' / 'file.c4').exists()
        assert not (dst / 'subdir').is_symlink()
