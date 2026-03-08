"""Tests for archi2likec4.config module."""

import pytest
from pathlib import Path

from archi2likec4.config import ConvertConfig, load_config, _apply_yaml
from archi2likec4.models import PROMOTE_CHILDREN, PROMOTE_WARN_THRESHOLD, DOMAIN_RENAMES


class TestConvertConfigDefaults:
    """Default config should match models.py constants."""

    def test_promote_children_defaults(self):
        config = ConvertConfig()
        assert config.promote_children == dict(PROMOTE_CHILDREN)

    def test_promote_warn_threshold_default(self):
        config = ConvertConfig()
        assert config.promote_warn_threshold == PROMOTE_WARN_THRESHOLD

    def test_domain_renames_defaults(self):
        config = ConvertConfig()
        assert config.domain_renames == dict(DOMAIN_RENAMES)

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
        assert config.promote_children == dict(PROMOTE_CHILDREN)

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

    def test_strict_override(self):
        config = ConvertConfig()
        _apply_yaml(config, {'strict': True})
        assert config.strict is True

    def test_unrecognized_keys_ignored(self):
        config = ConvertConfig()
        _apply_yaml(config, {'unknown_key': 42, 'another': 'value'})
        # Should not raise, defaults unchanged
        assert config.promote_children == dict(PROMOTE_CHILDREN)

    def test_invalid_type_ignored(self):
        config = ConvertConfig()
        # promote_children expects dict — string should be ignored
        _apply_yaml(config, {'promote_children': 'not a dict'})
        assert config.promote_children == dict(PROMOTE_CHILDREN)

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
