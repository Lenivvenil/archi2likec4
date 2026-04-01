"""Tests for archi2likec4.config module."""

import importlib.util
from pathlib import Path

import pytest

from archi2likec4.config import (
    _DEFAULT_DOMAIN_RENAMES,
    _DEFAULT_PROMOTE_CHILDREN,
    _DEFAULT_SPEC_COLORS,
    _DEFAULT_SPEC_SHAPES,
    _DEFAULT_SPEC_TAGS,
    _DEFAULT_SYNC_PROTECTED_PATHS,
    _DEFAULT_SYNC_PROTECTED_TOP,
    ConvertConfig,
    _apply_yaml,
    load_config,
)
from archi2likec4.exceptions import Archi2LikeC4Error, ConfigError
from archi2likec4.models import PROMOTE_WARN_THRESHOLD


class TestConvertConfigDefaults:
    """Default config should match config.py constants."""

    def test_promote_children_defaults(self):
        config = ConvertConfig()
        assert config.promote_children == dict(_DEFAULT_PROMOTE_CHILDREN)

    def test_promote_warn_threshold_default(self):
        config = ConvertConfig()
        assert config.promote_warn_threshold == PROMOTE_WARN_THRESHOLD

    def test_domain_renames_defaults(self):
        config = ConvertConfig()
        assert config.domain_renames == dict(_DEFAULT_DOMAIN_RENAMES)

    def test_quality_gate_defaults(self):
        config = ConvertConfig()
        assert config.max_unresolved_ratio == 0.5
        assert config.max_orphan_functions_warn == 5
        assert config.max_unassigned_systems_warn == 20

    def test_flags_default_false(self):
        config = ConvertConfig()
        assert config.strict is False
        assert config.verbose is False
        assert config.dry_run is False


class TestLoadConfig:
    """Config loading from YAML files."""

    def test_explicit_missing_path_raises(self):
        """Explicit --config with nonexistent file must raise."""
        with pytest.raises(FileNotFoundError, match='Config file not found'):
            load_config(Path('/nonexistent/path/config.yaml'))

    def test_load_none_returns_defaults(self, tmp_path, monkeypatch):
        # Change to tmp_path so auto-detect doesn't find a stale .archi2likec4.yaml
        monkeypatch.chdir(tmp_path)
        config = load_config(None)
        assert config.promote_children == dict(_DEFAULT_PROMOTE_CHILDREN)

    def test_yaml_root_list_raises(self, tmp_path):
        """YAML file with list at root must raise ValueError."""
        config_file = tmp_path / 'bad.yaml'
        config_file.write_text('- item1\n- item2\n')
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        with pytest.raises(ConfigError, match='expected YAML mapping at root'):
            load_config(config_file)


class TestApplyYaml:
    """YAML partial override logic."""

    def test_promote_children_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'promote_children': {'X': 'domain_x'}})
        assert config.promote_children == {'X': 'domain_x'}

    def test_promote_children_invalid_c4_id_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='invalid C4 identifier'):
            _apply_yaml(config, {'promote_children': {'X': 'Bad Domain'}})

    def test_promote_warn_threshold_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'promote_warn_threshold': 20})
        assert config.promote_warn_threshold == 20

    def test_domain_renames_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {
            'domain_renames': {
                'old': ['new', 'New Domain'],
            }
        })
        assert config.domain_renames == {'old': ('new', 'New Domain')}

    def test_extra_domain_patterns_override(self):
        config = ConvertConfig()
        patterns = [{'c4_id': 'custom', 'name': 'Custom', 'patterns': ['foo']}]
        _apply_yaml(config, {'extra_domain_patterns': patterns})
        assert config.extra_domain_patterns == patterns

    def test_quality_gates_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {
            'quality_gates': {
                'max_unresolved_ratio': 0.3,
                'max_orphan_functions_warn': 10,
                'max_unassigned_systems_warn': 50,
            }
        })
        assert config.max_unresolved_ratio == 0.3
        assert config.max_orphan_functions_warn == 10
        assert config.max_unassigned_systems_warn == 50

    def test_partial_quality_gates(self):
        config = ConvertConfig()
        _apply_yaml(config, {
            'quality_gates': {'max_unresolved_ratio': 0.7}
        })
        assert config.max_unresolved_ratio == 0.7
        # Other gates unchanged
        assert config.max_orphan_functions_warn == 5
        assert config.max_unassigned_systems_warn == 20

    def test_max_unresolved_ratio_bounds(self):
        """max_unresolved_ratio must be between 0 and 1."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='between 0 and 1'):
            _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': -0.1}})
        with pytest.raises(ConfigError, match='between 0 and 1'):
            _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': 1.5}})
        # Valid boundary values
        _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': 0}})
        assert config.max_unresolved_ratio == 0
        _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': 1}})
        assert config.max_unresolved_ratio == 1

    def test_negative_promote_warn_threshold(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='non-negative'):
            _apply_yaml(config, {'promote_warn_threshold': -1})

    def test_negative_max_orphan_functions_warn(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='non-negative'):
            _apply_yaml(config, {'quality_gates': {'max_orphan_functions_warn': -5}})

    def test_negative_max_unassigned_systems_warn(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='non-negative'):
            _apply_yaml(config, {'quality_gates': {'max_unassigned_systems_warn': -1}})

    def test_extra_domain_patterns_items_must_be_strings(self):
        """Pattern items in extra_domain_patterns must be strings."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='expected string'):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 'test', 'name': 'Test', 'patterns': [123]}
            ]})

    def test_strict_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'strict': True})
        assert config.strict is True

    def test_audit_suppress_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'audit_suppress': ['SystemA', 'SystemB']})
        assert config.audit_suppress == ['SystemA', 'SystemB']

    def test_audit_suppress_default_empty(self):
        config = ConvertConfig()
        assert config.audit_suppress == []

    def test_unrecognized_keys_warned(self, caplog):
        import logging
        config = ConvertConfig()
        with caplog.at_level(logging.WARNING, logger='archi2likec4.config'):
            _apply_yaml(config, {'unknown_key': 42, 'another': 'value'})
        assert 'Unknown config keys' in caplog.text
        assert 'another' in caplog.text
        assert 'unknown_key' in caplog.text
        # Defaults unchanged
        assert config.promote_children == dict(_DEFAULT_PROMOTE_CHILDREN)

    def test_invalid_type_raises(self):
        config = ConvertConfig()
        # promote_children expects dict — string must raise ValueError
        with pytest.raises(ConfigError, match='promote_children.*expected mapping'):
            _apply_yaml(config, {'promote_children': 'not a dict'})

    def test_domain_renames_invalid_shape_string(self):
        """String value instead of [id, name] must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="domain_renames\\['x'\\]"):
            _apply_yaml(config, {'domain_renames': {'x': 'bad'}})

    def test_domain_renames_wrong_length(self):
        """List with != 2 elements must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="domain_renames\\['x'\\]"):
            _apply_yaml(config, {'domain_renames': {'x': ['only_one']}})

    def test_domain_renames_too_many_elements(self):
        """List with 3 elements must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="domain_renames\\['y'\\]"):
            _apply_yaml(config, {'domain_renames': {'y': ['a', 'b', 'c']}})

    def test_domain_renames_invalid_c4_id(self):
        """Invalid C4 identifier in domain_renames must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="invalid C4 identifier"):
            _apply_yaml(config, {'domain_renames': {'old': ['../../escape', 'Bad']}})

    def test_domain_renames_path_traversal_rejected(self):
        """Path traversal in c4_id must be rejected."""
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="invalid C4 identifier"):
            _apply_yaml(config, {'domain_renames': {'old': ['../etc/passwd', 'Hack']}})

    def test_domain_renames_valid_c4_id_accepted(self):
        """Valid C4 identifier in domain_renames must be accepted."""
        config = ConvertConfig()
        _apply_yaml(config, {'domain_renames': {'old': ['new_domain', 'New Domain']}})
        assert config.domain_renames == {'old': ('new_domain', 'New Domain')}

    def test_full_yaml_file(self, tmp_path):
        """Load a complete YAML config file."""
        yaml_content = """\
promote_children:
  TestParent: test_domain

promote_warn_threshold: 15

domain_renames:
  old_id: [new_id, "New Name"]

extra_domain_patterns:
  - c4_id: test_domain
    name: "Test Domain"
    patterns: [TestA, TestB]

quality_gates:
  max_unresolved_ratio: 0.3
  max_orphan_functions_warn: 2
  max_unassigned_systems_warn: 10

strict: true
"""
        config_file = tmp_path / 'config.yaml'
        config_file.write_text(yaml_content)

        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')

        config = load_config(config_file)
        assert config.promote_children == {'TestParent': 'test_domain'}
        assert config.promote_warn_threshold == 15
        assert config.domain_renames == {'old_id': ('new_id', 'New Name')}
        assert len(config.extra_domain_patterns) == 1
        assert config.max_unresolved_ratio == 0.3
        assert config.max_orphan_functions_warn == 2
        assert config.max_unassigned_systems_warn == 10
        assert config.strict is True


class TestStrictBoolParsing:
    """P1-3: bool('false') should not become True."""

    def test_strict_string_false(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        _apply_yaml(config, {'strict': 'false'})
        assert config.strict is False

    def test_strict_string_true(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        _apply_yaml(config, {'strict': 'true'})
        assert config.strict is True

    def test_strict_bool_native(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        _apply_yaml(config, {'strict': False})
        assert config.strict is False


class TestExtraDomainPatternsValidation:
    """P1-4: invalid extra_domain_patterns should raise ValueError."""

    def test_missing_key(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='missing required key'):
            _apply_yaml(config, {'extra_domain_patterns': [{'foo': 'bar'}]})

    def test_patterns_not_list(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='expected list'):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 'x', 'name': 'X', 'patterns': 'not-a-list'}
            ]})

    def test_entry_not_dict(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='expected mapping'):
            _apply_yaml(config, {'extra_domain_patterns': ['just-a-string']})

    def test_c4_id_must_be_string(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="c4_id.*expected string"):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 123, 'name': 'X', 'patterns': ['a']}
            ]})

    def test_invalid_c4_id_raises(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='invalid C4 identifier'):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 'bad id', 'name': 'X', 'patterns': ['a']}
            ]})

    def test_name_must_be_string(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="name.*expected string"):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 'x', 'name': 42, 'patterns': ['a']}
            ]})


class TestAuditSuppressIncidents:
    """audit_suppress_incidents config option."""

    def test_default_empty(self):
        config = ConvertConfig()
        assert config.audit_suppress_incidents == []

    def test_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'audit_suppress_incidents': ['QA-5', 'QA-6']})
        assert config.audit_suppress_incidents == ['QA-5', 'QA-6']

    def test_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='audit_suppress_incidents.*expected list'):
            _apply_yaml(config, {'audit_suppress_incidents': 'QA-5'})

    def test_audit_suppress_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='audit_suppress.*expected list'):
            _apply_yaml(config, {'audit_suppress': 'SystemA'})


class TestSaveSuppress:
    """save_suppress() writes YAML correctly."""

    def test_creates_yaml(self, tmp_path):
        from archi2likec4.config import save_suppress
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        config_file = tmp_path / '.archi2likec4.yaml'
        save_suppress(config_file, ['SystemA'], ['QA-5'])
        assert config_file.exists()
        data = yaml.safe_load(config_file.read_text())
        assert data['audit_suppress'] == ['SystemA']
        assert data['audit_suppress_incidents'] == ['QA-5']

    def test_preserves_other_keys(self, tmp_path):
        from archi2likec4.config import save_suppress
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        config_file = tmp_path / '.archi2likec4.yaml'
        config_file.write_text('promote_warn_threshold: 15\n')
        save_suppress(config_file, ['X'], [])
        data = yaml.safe_load(config_file.read_text())
        assert data['promote_warn_threshold'] == 15
        assert data['audit_suppress'] == ['X']
        assert 'audit_suppress_incidents' not in data  # empty list not written

    def test_removes_empty_lists(self, tmp_path):
        from archi2likec4.config import save_suppress
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        config_file = tmp_path / '.archi2likec4.yaml'
        config_file.write_text('audit_suppress:\n  - Old\n')
        save_suppress(config_file, [], [])
        data = yaml.safe_load(config_file.read_text())
        assert data is None or 'audit_suppress' not in (data or {})


    def test_list_root_yaml_not_crash(self, tmp_path):
        """save_suppress should handle YAML file with list root gracefully."""
        from archi2likec4.config import save_suppress
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        config_file = tmp_path / '.archi2likec4.yaml'
        config_file.write_text('- item1\n- item2\n')
        save_suppress(config_file, ['Sys'], [])
        data = yaml.safe_load(config_file.read_text())
        assert data['audit_suppress'] == ['Sys']


class TestMutableDefaults:
    """P2-8: mutable defaults should not leak between instances."""

    def test_extra_domain_patterns_isolated(self):
        from archi2likec4.config import ConvertConfig
        c1 = ConvertConfig()
        c2 = ConvertConfig()
        c1.extra_domain_patterns.append({'c4_id': 'x', 'name': 'X', 'patterns': ['a']})
        assert len(c2.extra_domain_patterns) == 0


class TestLanguageConfig:
    """language config option."""

    def test_default_ru(self):
        config = ConvertConfig()
        assert config.language == 'ru'

    def test_yaml_en(self):
        config = ConvertConfig()
        _apply_yaml(config, {'language': 'en'})
        assert config.language == 'en'

    def test_invalid_language_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="language.*expected 'ru' or 'en'"):
            _apply_yaml(config, {'language': 'fr'})


class TestDeploymentEnvConfig:
    """deployment_env config option."""

    def test_default_prod(self):
        config = ConvertConfig()
        assert config.deployment_env == 'prod'

    def test_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'deployment_env': 'staging'})
        assert config.deployment_env == 'staging'

    def test_empty_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='deployment_env.*must not be empty'):
            _apply_yaml(config, {'deployment_env': '  '})

    def test_invalid_c4_id_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='deployment_env.*invalid C4 identifier'):
            _apply_yaml(config, {'deployment_env': 'prod west'})

    def test_uppercase_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='deployment_env.*invalid C4 identifier'):
            _apply_yaml(config, {'deployment_env': 'Prod'})

    def test_in_known_keys(self):
        from archi2likec4.config import _KNOWN_YAML_KEYS
        assert 'deployment_env' in _KNOWN_YAML_KEYS


class TestDomainOverrides:
    """domain_overrides config option."""

    def test_default_empty(self):
        config = ConvertConfig()
        assert config.domain_overrides == {}

    def test_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'domain_overrides': {'CRM': 'products', 'AD': 'platform'}})
        assert config.domain_overrides == {'CRM': 'products', 'AD': 'platform'}

    def test_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='domain_overrides.*expected mapping'):
            _apply_yaml(config, {'domain_overrides': 'not-a-dict'})

    def test_invalid_c4_id_value_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='invalid C4 identifier'):
            _apply_yaml(config, {'domain_overrides': {'CRM': 'bad id'}})


class TestSubdomainOverrides:
    """subdomain_overrides config option."""

    def test_default_empty(self):
        config = ConvertConfig()
        assert config.subdomain_overrides == {}

    def test_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'subdomain_overrides': {'PaymentCore': 'payments', 'Reports': 'analytics'}})
        assert config.subdomain_overrides == {'PaymentCore': 'payments', 'Reports': 'analytics'}

    def test_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='subdomain_overrides.*expected mapping'):
            _apply_yaml(config, {'subdomain_overrides': 'not-a-dict'})

    def test_invalid_c4_id_value_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='invalid C4 identifier'):
            _apply_yaml(config, {'subdomain_overrides': {'CRM': 'bad id'}})

    def test_not_flagged_as_unknown_key(self):
        """subdomain_overrides must be recognized — no warning logged."""
        from archi2likec4.config import _KNOWN_YAML_KEYS
        assert 'subdomain_overrides' in _KNOWN_YAML_KEYS


class TestReviewedSystems:
    """reviewed_systems config option."""

    def test_default_empty(self):
        config = ConvertConfig()
        assert config.reviewed_systems == []

    def test_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'reviewed_systems': ['SysA', 'SysB']})
        assert config.reviewed_systems == ['SysA', 'SysB']

    def test_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='reviewed_systems.*expected list'):
            _apply_yaml(config, {'reviewed_systems': 'not-a-list'})


class TestUpdateConfigField:
    """update_config_field() writes YAML correctly."""

    def test_creates_file(self, tmp_path):
        from archi2likec4.config import update_config_field
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        f = tmp_path / '.archi2likec4.yaml'
        update_config_field(f, 'domain_overrides', {'CRM': 'products'})
        data = yaml.safe_load(f.read_text())
        assert data['domain_overrides'] == {'CRM': 'products'}

    def test_preserves_other_keys(self, tmp_path):
        from archi2likec4.config import update_config_field
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        f = tmp_path / '.archi2likec4.yaml'
        f.write_text('promote_warn_threshold: 15\n')
        update_config_field(f, 'reviewed_systems', ['Sys1'])
        data = yaml.safe_load(f.read_text())
        assert data['promote_warn_threshold'] == 15
        assert data['reviewed_systems'] == ['Sys1']

    def test_removes_empty_dict(self, tmp_path):
        from archi2likec4.config import update_config_field
        if importlib.util.find_spec('yaml') is None:
            pytest.skip('PyYAML not installed')
        import yaml
        f = tmp_path / '.archi2likec4.yaml'
        f.write_text('domain_overrides:\n  CRM: products\n')
        update_config_field(f, 'domain_overrides', {})
        data = yaml.safe_load(f.read_text())
        assert data is None or 'domain_overrides' not in (data or {})


class TestStrictValidation:
    """strict field should reject invalid types and unrecognised strings."""

    def test_strict_list_rejected(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='strict.*expected bool or string'):
            _apply_yaml(config, {'strict': ['x']})

    def test_strict_int_rejected(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='strict.*expected bool or string'):
            _apply_yaml(config, {'strict': 42})

    def test_strict_unknown_string_rejected(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="strict.*got 'tru'"):
            _apply_yaml(config, {'strict': 'tru'})


class TestListItemTypeValidation:
    """List config fields should reject non-string items."""

    def test_audit_suppress_non_string_item(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='audit_suppress.*must be strings'):
            _apply_yaml(config, {'audit_suppress': ['ok', 123]})

    def test_audit_suppress_incidents_non_string_item(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='audit_suppress_incidents.*must be strings'):
            _apply_yaml(config, {'audit_suppress_incidents': ['QA-1', ['nested']]})

    def test_reviewed_systems_non_string_item(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='reviewed_systems.*must be strings'):
            _apply_yaml(config, {'reviewed_systems': [None]})


class TestSyncTarget:
    """sync_target config option."""

    def test_default_none(self):
        config = ConvertConfig()
        assert config.sync_target is None

    def test_yaml_valid_directory(self, tmp_path):
        config = ConvertConfig()
        _apply_yaml(config, {'sync_target': str(tmp_path)})
        assert config.sync_target == tmp_path.resolve()

    def test_yaml_none_clears_target(self):
        config = ConvertConfig()
        config.sync_target = Path('/tmp')
        _apply_yaml(config, {'sync_target': None})
        assert config.sync_target is None

    def test_yaml_nonexistent_raises(self, tmp_path):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_target.*does not exist'):
            _apply_yaml(config, {'sync_target': str(tmp_path / 'no_such_dir')})

    def test_yaml_file_raises(self, tmp_path):
        f = tmp_path / 'file.txt'
        f.write_text('x')
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_target.*not a directory'):
            _apply_yaml(config, {'sync_target': str(f)})

    def test_yaml_non_string_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_target.*expected string path'):
            _apply_yaml(config, {'sync_target': 42})

    def test_known_yaml_key(self):
        from archi2likec4.config import _KNOWN_YAML_KEYS
        assert 'sync_target' in _KNOWN_YAML_KEYS


class TestSyncOutput:
    """_sync_output() copies files and respects protected list."""

    def _make_output(self, output_dir: Path) -> None:
        """Create a minimal fake output/ tree."""
        (output_dir / '.archi2likec4-output').write_text('')
        (output_dir / 'domains').mkdir()
        (output_dir / 'domains' / 'products.c4').write_text('domain products {}')
        (output_dir / 'AUDIT.md').write_text('# Audit')
        scripts = output_dir / 'scripts'
        scripts.mkdir()
        (scripts / 'federate.py').write_text('# federate')

    def test_copies_generated_files(self, tmp_path):
        from archi2likec4.pipeline import _sync_output

        output_dir = tmp_path / 'output'
        output_dir.mkdir()
        self._make_output(output_dir)

        sync_target = tmp_path / 'target'
        sync_target.mkdir()

        config = ConvertConfig()
        config.output_dir = output_dir
        config.sync_target = sync_target

        _sync_output(config)

        assert (sync_target / 'AUDIT.md').exists()
        assert (sync_target / 'domains' / 'products.c4').exists()
        assert (sync_target / 'scripts' / 'federate.py').exists()

    def test_skips_protected_files(self, tmp_path):
        from archi2likec4.pipeline import _sync_output

        output_dir = tmp_path / 'output'
        output_dir.mkdir()
        self._make_output(output_dir)
        # Add a protected file in output that should NOT be copied
        (output_dir / 'README.md').write_text('generated readme')

        sync_target = tmp_path / 'target'
        sync_target.mkdir()
        # Pre-existing protected file in target
        (sync_target / 'README.md').write_text('original readme')

        config = ConvertConfig()
        config.output_dir = output_dir
        config.sync_target = sync_target
        config.sync_protected_top = frozenset({'README.md'})

        _sync_output(config)

        # Protected file in target must be untouched
        assert (sync_target / 'README.md').read_text() == 'original readme'

    def test_skips_protected_directory_with_trailing_slash(self, tmp_path):
        """Directories specified with trailing slash in config must still be protected."""
        from archi2likec4.pipeline import _sync_output

        output_dir = tmp_path / 'output'
        output_dir.mkdir()
        self._make_output(output_dir)
        # Add an adr directory in output that should NOT overwrite target
        (output_dir / 'adr').mkdir()
        (output_dir / 'adr' / 'generated.md').write_text('generated adr')

        sync_target = tmp_path / 'target'
        sync_target.mkdir()
        (sync_target / 'adr').mkdir()
        (sync_target / 'adr' / 'original.md').write_text('original adr')

        config = ConvertConfig()
        config.output_dir = output_dir
        config.sync_target = sync_target
        # User writes 'adr/' with trailing slash, as documented in the example YAML
        config.sync_protected_top = frozenset({'adr'})

        _sync_output(config)

        # Protected directory contents must be untouched
        assert (sync_target / 'adr' / 'original.md').read_text() == 'original adr'
        assert not (sync_target / 'adr' / 'generated.md').exists()

    def test_noop_when_no_sync_target(self, tmp_path):
        from archi2likec4.pipeline import _sync_output

        config = ConvertConfig()
        config.output_dir = tmp_path / 'output'
        config.sync_target = None
        # Should not raise and return True (no-op success)
        assert _sync_output(config) is True



class TestPropertyMapConfig:
    """property_map and standard_keys config options."""

    def test_property_map_default_equals_default_prop_map(self):
        from archi2likec4.models import DEFAULT_PROP_MAP
        config = ConvertConfig()
        assert config.property_map == DEFAULT_PROP_MAP

    def test_standard_keys_default_equals_default_standard_keys(self):
        from archi2likec4.models import DEFAULT_STANDARD_KEYS
        config = ConvertConfig()
        assert config.standard_keys == DEFAULT_STANDARD_KEYS

    def test_property_map_yaml_override(self):
        from archi2likec4.models import DEFAULT_PROP_MAP
        config = ConvertConfig()
        _apply_yaml(config, {'property_map': {'MyProp': 'my_key', 'CI': 'ci_override'}})
        # YAML entries are merged on top of defaults, not replacing them
        assert config.property_map['MyProp'] == 'my_key'
        assert config.property_map['CI'] == 'ci_override'
        # Default keys not overridden by YAML are still present
        for key in DEFAULT_PROP_MAP:
            if key != 'CI':
                assert key in config.property_map

    def test_standard_keys_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'standard_keys': ['my_key', 'other_key']})
        assert config.standard_keys == ['my_key', 'other_key']

    def test_property_map_not_dict_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='property_map.*expected mapping'):
            _apply_yaml(config, {'property_map': ['not', 'a', 'dict']})

    def test_property_map_non_string_value_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='property_map.*must be strings'):
            _apply_yaml(config, {'property_map': {'Key': 123}})

    def test_standard_keys_not_list_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='standard_keys.*expected list'):
            _apply_yaml(config, {'standard_keys': 'not-a-list'})

    def test_standard_keys_non_string_item_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='standard_keys.*must be strings'):
            _apply_yaml(config, {'standard_keys': ['ok', 42]})

    def test_property_map_isolated_between_instances(self):
        c1 = ConvertConfig()
        c2 = ConvertConfig()
        c1.property_map['NewKey'] = 'new_val'
        assert 'NewKey' not in c2.property_map


class TestSyncProtectedConfig:
    """sync_protected_top and sync_protected_paths config options."""

    def test_defaults_use_builtin_protected_sets(self):
        config = ConvertConfig()
        assert config.sync_protected_top == _DEFAULT_SYNC_PROTECTED_TOP
        assert config.sync_protected_paths == _DEFAULT_SYNC_PROTECTED_PATHS
        # Verify well-known artefacts are protected by default
        assert 'README.md' in config.sync_protected_top
        assert '.gitignore' in config.sync_protected_top
        assert 'adr' in config.sync_protected_top
        assert 'scripts/check_staleness.py' in config.sync_protected_paths

    def test_sync_protected_top_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'sync_protected_top': ['README.md', '.gitignore']})
        assert config.sync_protected_top == frozenset({'README.md', '.gitignore'})

    def test_sync_protected_paths_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'sync_protected_paths': ['scripts/check.py', 'adr/']})
        assert config.sync_protected_paths == frozenset({'scripts/check.py', 'adr'})

    def test_sync_protected_top_trailing_slash_normalized(self):
        config = ConvertConfig()
        _apply_yaml(config, {'sync_protected_top': ['adr/', 'dist/']})
        assert config.sync_protected_top == frozenset({'adr', 'dist'})

    def test_sync_protected_paths_trailing_slash_normalized(self):
        config = ConvertConfig()
        _apply_yaml(config, {'sync_protected_paths': ['scripts/', 'docs/api/']})
        assert config.sync_protected_paths == frozenset({'scripts', 'docs/api'})

    def test_sync_protected_top_not_list_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_protected_top.*expected list'):
            _apply_yaml(config, {'sync_protected_top': 'README.md'})

    def test_sync_protected_paths_not_list_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_protected_paths.*expected list'):
            _apply_yaml(config, {'sync_protected_paths': {'key': 'val'}})

    def test_sync_protected_top_non_string_item_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_protected_top.*must be strings'):
            _apply_yaml(config, {'sync_protected_top': ['ok', 42]})

    def test_sync_protected_paths_non_string_item_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='sync_protected_paths.*must be strings'):
            _apply_yaml(config, {'sync_protected_paths': [None]})

    def test_known_yaml_keys(self):
        from archi2likec4.config import _KNOWN_YAML_KEYS
        assert 'sync_protected_top' in _KNOWN_YAML_KEYS
        assert 'sync_protected_paths' in _KNOWN_YAML_KEYS


# ── Spec config (Issue #29) ───────────────────────────────────────────────

class TestSpecConfig:
    """spec_colors, spec_shapes, spec_tags config options."""

    def test_defaults_use_builtin_spec_values(self):
        config = ConvertConfig()
        assert config.spec_colors == _DEFAULT_SPEC_COLORS
        assert config.spec_shapes == _DEFAULT_SPEC_SHAPES
        assert config.spec_tags == _DEFAULT_SPEC_TAGS

    def test_spec_colors_yaml_merge(self):
        config = ConvertConfig()
        _apply_yaml(config, {'spec_colors': {'archi-app': '#FF0000', 'custom': '#123456'}})
        assert config.spec_colors['archi-app'] == '#FF0000'
        assert config.spec_colors['custom'] == '#123456'
        # Other defaults preserved
        assert config.spec_colors['archi-data'] == '#F0D68A'

    def test_spec_shapes_yaml_merge(self):
        config = ConvertConfig()
        _apply_yaml(config, {'spec_shapes': {'domain': 'hexagon'}})
        assert config.spec_shapes['domain'] == 'hexagon'
        # Other defaults preserved
        assert config.spec_shapes['system'] == 'component'

    def test_spec_tags_yaml_merge(self):
        config = ConvertConfig()
        _apply_yaml(config, {'spec_tags': ['custom_tag']})
        # Merges with defaults (like colors/shapes), not replaces
        for tag in _DEFAULT_SPEC_TAGS:
            assert tag in config.spec_tags
        assert 'custom_tag' in config.spec_tags

    def test_spec_colors_not_dict_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_colors.*expected mapping'):
            _apply_yaml(config, {'spec_colors': ['not', 'a', 'dict']})

    def test_spec_shapes_not_dict_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_shapes.*expected mapping'):
            _apply_yaml(config, {'spec_shapes': 'flat'})

    def test_spec_tags_not_list_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_tags.*expected list'):
            _apply_yaml(config, {'spec_tags': {'not': 'a list'}})

    def test_spec_tags_non_string_item_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_tags.*must be strings'):
            _apply_yaml(config, {'spec_tags': ['ok', 42]})

    def test_spec_colors_non_string_value_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_colors.*must be strings'):
            _apply_yaml(config, {'spec_colors': {'archi-app': 123}})

    def test_spec_colors_invalid_key_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_colors.*invalid C4 identifier'):
            _apply_yaml(config, {'spec_colors': {'my color': '#FF0000'}})

    def test_spec_shapes_invalid_key_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_shapes.*unknown element kind'):
            _apply_yaml(config, {'spec_shapes': {'My Shape': 'rectangle'}})

    def test_spec_shapes_rejects_unknown_c4_identifier(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_shapes.*unknown element kind'):
            _apply_yaml(config, {'spec_shapes': {'custom_kind': 'hexagon'}})

    def test_spec_shapes_accepts_camelcase_element_kinds(self):
        config = ConvertConfig()
        _apply_yaml(config, {'spec_shapes': {'appFunction': 'hexagon', 'dataStore': 'rectangle'}})
        assert config.spec_shapes['appFunction'] == 'hexagon'
        assert config.spec_shapes['dataStore'] == 'rectangle'

    def test_spec_tags_invalid_id_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='spec_tags.*invalid C4 identifier'):
            _apply_yaml(config, {'spec_tags': ['needs review']})

    def test_known_yaml_keys_include_spec(self):
        from archi2likec4.config import _KNOWN_YAML_KEYS
        assert 'spec_colors' in _KNOWN_YAML_KEYS
        assert 'spec_shapes' in _KNOWN_YAML_KEYS
        assert 'spec_tags' in _KNOWN_YAML_KEYS


# ── Bank-specific defaults (Issue #6) ────────────────────────────────────

class TestBankSpecificDefaults:
    """Issue #6: organization-specific defaults must be empty; values go in .archi2likec4.yaml."""

    def test_default_domain_renames_is_empty(self):
        assert _DEFAULT_DOMAIN_RENAMES == {}

    def test_default_promote_children_is_empty(self):
        assert _DEFAULT_PROMOTE_CHILDREN == {}

    def test_default_extra_domain_patterns_is_empty(self):
        from archi2likec4.config import _DEFAULT_EXTRA_DOMAIN_PATTERNS
        assert _DEFAULT_EXTRA_DOMAIN_PATTERNS == []


class TestExtraViewPatterns:
    """extra_view_patterns config loading and validation."""

    def test_default_has_three_russian_patterns(self):
        config = ConvertConfig()
        assert len(config.extra_view_patterns) == 3
        types = [p['view_type'] for p in config.extra_view_patterns]
        assert 'functional' in types
        assert 'integration' in types
        assert 'deployment' in types

    def test_load_from_yaml(self):
        config = ConvertConfig()
        _apply_yaml(config, {'extra_view_patterns': [
            {'pattern': r'^Custom\.(.+)$', 'view_type': 'functional'},
        ]})
        assert len(config.extra_view_patterns) == 1
        assert config.extra_view_patterns[0]['view_type'] == 'functional'

    def test_empty_list_clears_patterns(self):
        config = ConvertConfig()
        _apply_yaml(config, {'extra_view_patterns': []})
        assert config.extra_view_patterns == []

    def test_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='expected list'):
            _apply_yaml(config, {'extra_view_patterns': 'bad'})

    def test_missing_key_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="missing required key 'view_type'"):
            _apply_yaml(config, {'extra_view_patterns': [{'pattern': r'^X$'}]})

    def test_invalid_view_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match="must be 'functional'"):
            _apply_yaml(config, {'extra_view_patterns': [
                {'pattern': r'^X$', 'view_type': 'unknown'},
            ]})

    def test_invalid_regex_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='invalid regex'):
            _apply_yaml(config, {'extra_view_patterns': [
                {'pattern': r'[invalid', 'view_type': 'functional'},
            ]})

    def test_entry_not_mapping_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='expected mapping'):
            _apply_yaml(config, {'extra_view_patterns': ['bad']})


class TestTrashFolderConfig:
    """trash_folder config option."""

    def test_default_value(self):
        config = ConvertConfig()
        assert config.trash_folder == '!РАЗБОР'

    def test_yaml_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'trash_folder': '!REVIEW'})
        assert config.trash_folder == '!REVIEW'

    def test_not_string_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='trash_folder.*expected string'):
            _apply_yaml(config, {'trash_folder': 123})

    def test_empty_string_raises(self):
        config = ConvertConfig()
        with pytest.raises(ConfigError, match='trash_folder.*must not be empty'):
            _apply_yaml(config, {'trash_folder': '  '})

    def test_known_yaml_keys(self):
        from archi2likec4.config import _KNOWN_YAML_KEYS
        assert 'trash_folder' in _KNOWN_YAML_KEYS


class TestExceptionHierarchy:
    """Verify exception class relationships."""

    def test_config_error_is_subclass(self):
        assert issubclass(ConfigError, Archi2LikeC4Error)
