"""Tests for archi2likec4.config module."""

from pathlib import Path

import pytest

from archi2likec4.config import (
    _DEFAULT_DOMAIN_RENAMES,
    _DEFAULT_PROMOTE_CHILDREN,
    ConvertConfig,
    _apply_yaml,
    load_config,
)
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
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip('PyYAML not installed')
        with pytest.raises(ValueError, match='expected YAML mapping at root'):
            load_config(config_file)


class TestApplyYaml:
    """YAML partial override logic."""

    def test_promote_children_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'promote_children': {'X': 'domain_x'}})
        assert config.promote_children == {'X': 'domain_x'}

    def test_promote_children_invalid_c4_id_raises(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='invalid C4 identifier'):
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
        with pytest.raises(ValueError, match='between 0 and 1'):
            _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': -0.1}})
        with pytest.raises(ValueError, match='between 0 and 1'):
            _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': 1.5}})
        # Valid boundary values
        _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': 0}})
        assert config.max_unresolved_ratio == 0
        _apply_yaml(config, {'quality_gates': {'max_unresolved_ratio': 1}})
        assert config.max_unresolved_ratio == 1

    def test_negative_promote_warn_threshold(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='non-negative'):
            _apply_yaml(config, {'promote_warn_threshold': -1})

    def test_negative_max_orphan_functions_warn(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='non-negative'):
            _apply_yaml(config, {'quality_gates': {'max_orphan_functions_warn': -5}})

    def test_negative_max_unassigned_systems_warn(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='non-negative'):
            _apply_yaml(config, {'quality_gates': {'max_unassigned_systems_warn': -1}})

    def test_extra_domain_patterns_items_must_be_strings(self):
        """Pattern items in extra_domain_patterns must be strings."""
        config = ConvertConfig()
        with pytest.raises(ValueError, match='expected string'):
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
        with pytest.raises(ValueError, match='promote_children.*expected mapping'):
            _apply_yaml(config, {'promote_children': 'not a dict'})

    def test_domain_renames_invalid_shape_string(self):
        """String value instead of [id, name] must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ValueError, match="domain_renames\\['x'\\]"):
            _apply_yaml(config, {'domain_renames': {'x': 'bad'}})

    def test_domain_renames_wrong_length(self):
        """List with != 2 elements must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ValueError, match="domain_renames\\['x'\\]"):
            _apply_yaml(config, {'domain_renames': {'x': ['only_one']}})

    def test_domain_renames_too_many_elements(self):
        """List with 3 elements must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ValueError, match="domain_renames\\['y'\\]"):
            _apply_yaml(config, {'domain_renames': {'y': ['a', 'b', 'c']}})

    def test_domain_renames_invalid_c4_id(self):
        """Invalid C4 identifier in domain_renames must raise ValueError."""
        config = ConvertConfig()
        with pytest.raises(ValueError, match="invalid C4 identifier"):
            _apply_yaml(config, {'domain_renames': {'old': ['../../escape', 'Bad']}})

    def test_domain_renames_path_traversal_rejected(self):
        """Path traversal in c4_id must be rejected."""
        config = ConvertConfig()
        with pytest.raises(ValueError, match="invalid C4 identifier"):
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

        try:
            import yaml  # noqa: F401
        except ImportError:
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
        with pytest.raises(ValueError, match='missing required key'):
            _apply_yaml(config, {'extra_domain_patterns': [{'foo': 'bar'}]})

    def test_patterns_not_list(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ValueError, match='expected list'):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 'x', 'name': 'X', 'patterns': 'not-a-list'}
            ]})

    def test_entry_not_dict(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ValueError, match='expected mapping'):
            _apply_yaml(config, {'extra_domain_patterns': ['just-a-string']})

    def test_c4_id_must_be_string(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ValueError, match="c4_id.*expected string"):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 123, 'name': 'X', 'patterns': ['a']}
            ]})

    def test_invalid_c4_id_raises(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ValueError, match='invalid C4 identifier'):
            _apply_yaml(config, {'extra_domain_patterns': [
                {'c4_id': 'bad id', 'name': 'X', 'patterns': ['a']}
            ]})

    def test_name_must_be_string(self):
        from archi2likec4.config import ConvertConfig, _apply_yaml
        config = ConvertConfig()
        with pytest.raises(ValueError, match="name.*expected string"):
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
        with pytest.raises(ValueError, match='audit_suppress_incidents.*expected list'):
            _apply_yaml(config, {'audit_suppress_incidents': 'QA-5'})

    def test_audit_suppress_invalid_type_raises(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='audit_suppress.*expected list'):
            _apply_yaml(config, {'audit_suppress': 'SystemA'})


class TestSaveSuppress:
    """save_suppress() writes YAML correctly."""

    def test_creates_yaml(self, tmp_path):
        from archi2likec4.config import save_suppress
        try:
            import yaml  # noqa: F401
        except ImportError:
            import pytest
            pytest.skip('PyYAML not installed')
        config_file = tmp_path / '.archi2likec4.yaml'
        save_suppress(config_file, ['SystemA'], ['QA-5'])
        assert config_file.exists()
        data = yaml.safe_load(config_file.read_text())
        assert data['audit_suppress'] == ['SystemA']
        assert data['audit_suppress_incidents'] == ['QA-5']

    def test_preserves_other_keys(self, tmp_path):
        from archi2likec4.config import save_suppress
        try:
            import yaml  # noqa: F401
        except ImportError:
            import pytest
            pytest.skip('PyYAML not installed')
        config_file = tmp_path / '.archi2likec4.yaml'
        config_file.write_text('promote_warn_threshold: 15\n')
        save_suppress(config_file, ['X'], [])
        data = yaml.safe_load(config_file.read_text())
        assert data['promote_warn_threshold'] == 15
        assert data['audit_suppress'] == ['X']
        assert 'audit_suppress_incidents' not in data  # empty list not written

    def test_removes_empty_lists(self, tmp_path):
        from archi2likec4.config import save_suppress
        try:
            import yaml  # noqa: F401
        except ImportError:
            import pytest
            pytest.skip('PyYAML not installed')
        config_file = tmp_path / '.archi2likec4.yaml'
        config_file.write_text('audit_suppress:\n  - Old\n')
        save_suppress(config_file, [], [])
        data = yaml.safe_load(config_file.read_text())
        assert data is None or 'audit_suppress' not in (data or {})


    def test_list_root_yaml_not_crash(self, tmp_path):
        """save_suppress should handle YAML file with list root gracefully."""
        from archi2likec4.config import save_suppress
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip('PyYAML not installed')
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
        with pytest.raises(ValueError, match="language.*expected 'ru' or 'en'"):
            _apply_yaml(config, {'language': 'fr'})


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
        with pytest.raises(ValueError, match='domain_overrides.*expected mapping'):
            _apply_yaml(config, {'domain_overrides': 'not-a-dict'})

    def test_invalid_c4_id_value_raises(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='invalid C4 identifier'):
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
        with pytest.raises(ValueError, match='subdomain_overrides.*expected mapping'):
            _apply_yaml(config, {'subdomain_overrides': 'not-a-dict'})

    def test_invalid_c4_id_value_raises(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='invalid C4 identifier'):
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
        with pytest.raises(ValueError, match='reviewed_systems.*expected list'):
            _apply_yaml(config, {'reviewed_systems': 'not-a-list'})


class TestUpdateConfigField:
    """update_config_field() writes YAML correctly."""

    def test_creates_file(self, tmp_path):
        from archi2likec4.config import update_config_field
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip('PyYAML not installed')
        f = tmp_path / '.archi2likec4.yaml'
        update_config_field(f, 'domain_overrides', {'CRM': 'products'})
        data = yaml.safe_load(f.read_text())
        assert data['domain_overrides'] == {'CRM': 'products'}

    def test_preserves_other_keys(self, tmp_path):
        from archi2likec4.config import update_config_field
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip('PyYAML not installed')
        f = tmp_path / '.archi2likec4.yaml'
        f.write_text('promote_warn_threshold: 15\n')
        update_config_field(f, 'reviewed_systems', ['Sys1'])
        data = yaml.safe_load(f.read_text())
        assert data['promote_warn_threshold'] == 15
        assert data['reviewed_systems'] == ['Sys1']

    def test_removes_empty_dict(self, tmp_path):
        from archi2likec4.config import update_config_field
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip('PyYAML not installed')
        f = tmp_path / '.archi2likec4.yaml'
        f.write_text('domain_overrides:\n  CRM: products\n')
        update_config_field(f, 'domain_overrides', {})
        data = yaml.safe_load(f.read_text())
        assert data is None or 'domain_overrides' not in (data or {})


class TestStrictValidation:
    """strict field should reject invalid types and unrecognised strings."""

    def test_strict_list_rejected(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='strict.*expected bool or string'):
            _apply_yaml(config, {'strict': ['x']})

    def test_strict_int_rejected(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='strict.*expected bool or string'):
            _apply_yaml(config, {'strict': 42})

    def test_strict_unknown_string_rejected(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match="strict.*got 'tru'"):
            _apply_yaml(config, {'strict': 'tru'})


class TestListItemTypeValidation:
    """List config fields should reject non-string items."""

    def test_audit_suppress_non_string_item(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='audit_suppress.*must be strings'):
            _apply_yaml(config, {'audit_suppress': ['ok', 123]})

    def test_audit_suppress_incidents_non_string_item(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='audit_suppress_incidents.*must be strings'):
            _apply_yaml(config, {'audit_suppress_incidents': ['QA-1', ['nested']]})

    def test_reviewed_systems_non_string_item(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='reviewed_systems.*must be strings'):
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
        with pytest.raises(ValueError, match='sync_target.*does not exist'):
            _apply_yaml(config, {'sync_target': str(tmp_path / 'no_such_dir')})

    def test_yaml_file_raises(self, tmp_path):
        f = tmp_path / 'file.txt'
        f.write_text('x')
        config = ConvertConfig()
        with pytest.raises(ValueError, match='sync_target.*not a directory'):
            _apply_yaml(config, {'sync_target': str(f)})

    def test_yaml_non_string_raises(self):
        config = ConvertConfig()
        with pytest.raises(ValueError, match='sync_target.*expected string path'):
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

        _sync_output(config)

        # Protected file in target must be untouched
        assert (sync_target / 'README.md').read_text() == 'original readme'

    def test_noop_when_no_sync_target(self, tmp_path):
        from archi2likec4.pipeline import _sync_output

        config = ConvertConfig()
        config.output_dir = tmp_path / 'output'
        config.sync_target = None
        # Should not raise
        _sync_output(config)
