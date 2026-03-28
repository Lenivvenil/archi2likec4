"""Configuration: YAML file → dataclass, CLI defaults.

Organization-specific defaults (domain renames, extra patterns, promote
children) live here rather than in models.py so they can be overridden
via .archi2likec4.yaml without touching source code.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import ConfigError
from .models import DEFAULT_PROP_MAP, DEFAULT_STANDARD_KEYS, PROMOTE_WARN_THRESHOLD

logger = logging.getLogger(__name__)

_VALID_C4_ID = re.compile(r'^[a-z][a-z0-9_-]*$')


# ── Defaults ───────────────────────────────────────────────────────────
# Empty by default — organization-specific values belong in .archi2likec4.yaml.

_DEFAULT_DOMAIN_RENAMES: dict[str, tuple[str, str]] = {}

_DEFAULT_EXTRA_DOMAIN_PATTERNS: list[dict[str, Any]] = []

_DEFAULT_PROMOTE_CHILDREN: dict[str, str] = {}

# Russian-language view-name patterns shipped as defaults.
# Users can override via extra_view_patterns in .archi2likec4.yaml.
_DEFAULT_EXTRA_VIEW_PATTERNS: list[dict[str, str]] = [
    {'pattern': r'^Функциональная архитектура[.\s]+(.+)$', 'view_type': 'functional'},
    {'pattern': r'^Интеграционная архитектура[.\s]+(.+)$', 'view_type': 'integration'},
    {'pattern': r'^Схема разв[её]ртывания[.\s]+(.+)$', 'view_type': 'deployment'},
]

# Top-level names (files or entire dirs) never overwritten in sync target by default.
# These protect common companion-repo artefacts that must survive a re-sync.
# Can be overridden via sync_protected_top in .archi2likec4.yaml.
_DEFAULT_SYNC_PROTECTED_TOP: frozenset[str] = frozenset({
    '.gitignore',
    '.gitlab-ci.yml',
    '.gitlab',
    '.yamllint.yml',
    'AGENTS.md',
    'CLAUDE.md',
    'README.md',
    'adr',
    'dist',
    'fitness',
    'portal',
    'public',
    'static',
    'likec4.generated.ts',
    'gitlab-ci.yml',
})

# Specific relative sub-paths (POSIX) never overwritten in sync target by default.
_DEFAULT_SYNC_PROTECTED_PATHS: frozenset[str] = frozenset({
    'scripts/.gitkeep',
    'scripts/check_staleness.py',
    'scripts/validate_domains.py',
})

# Defaults for spec.py — custom color definitions, element shapes, and tags.
_DEFAULT_SPEC_COLORS: dict[str, str] = {
    'archi-app': '#7EB8DA',
    'archi-app-light': '#BDE0F0',
    'archi-data': '#F0D68A',
    'archi-store': '#B0B0B0',
    'archi-tech': '#93D275',
    'archi-tech-light': '#C5E6B8',
}

_DEFAULT_SPEC_SHAPES: dict[str, str] = {
    'domain': 'rectangle',
    'subdomain': 'rectangle',
    'system': 'component',
    'subsystem': 'component',
    'appFunction': 'rectangle',
    'dataEntity': 'document',
    'dataStore': 'cylinder',
    'infraNode': 'rectangle',
    'infraSoftware': 'cylinder',
    'infraZone': 'rectangle',
    'infraLocation': 'rectangle',
}

_DEFAULT_SPEC_TAGS: list[str] = [
    'to_review', 'external', 'entity', 'store',
    'infrastructure', 'cluster', 'device', 'network',
]


@dataclass
class ConvertConfig:
    """All tuneable parameters for the converter."""

    model_root: Path = field(default_factory=lambda: Path('architectural_repository/model'))
    output_dir: Path = field(default_factory=lambda: Path('output'))

    # Subsystem promotion
    promote_children: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_PROMOTE_CHILDREN))
    promote_warn_threshold: int = PROMOTE_WARN_THRESHOLD

    # Domain configuration
    domain_renames: dict[str, tuple[str, str]] = field(
        default_factory=lambda: dict(_DEFAULT_DOMAIN_RENAMES))
    extra_domain_patterns: list[dict[str, Any]] = field(
        default_factory=lambda: [dict(d, patterns=list(d['patterns']))
                                 for d in _DEFAULT_EXTRA_DOMAIN_PATTERNS])

    # Quality gates
    max_unresolved_ratio: float = 0.5
    max_orphan_functions_warn: int = 5
    max_unassigned_systems_warn: int = 20

    # Audit suppress-list: system names to exclude from AUDIT.md (accepted risks)
    audit_suppress: list[str] = field(default_factory=list)
    # Audit suppress by incident category: QA-IDs to hide entirely (e.g. ["QA-5", "QA-6"])
    audit_suppress_incidents: list[str] = field(default_factory=list)

    # Domain overrides: system name → domain c4_id (highest priority in assign_domains)
    domain_overrides: dict[str, str] = field(default_factory=dict)
    # Subdomain overrides: system name → subdomain c4_id (overrides folder-based auto-detection)
    subdomain_overrides: dict[str, str] = field(default_factory=dict)
    # Reviewed systems: strip to_review tag during build
    reviewed_systems: list[str] = field(default_factory=list)

    # i18n: language for AUDIT.md and Web UI ('ru' or 'en')
    language: str = 'ru'

    # Extra view-name regex patterns (locale-specific, e.g. Russian)
    extra_view_patterns: list[dict[str, str]] = field(
        default_factory=lambda: [dict(d) for d in _DEFAULT_EXTRA_VIEW_PATTERNS])

    # Deployment environment name used in LikeC4 deployment views
    deployment_env: str = 'prod'

    # Auto-sync: copy output_dir to this directory after generation
    sync_target: Path | None = None

    # Configurable metadata mapping (override DEFAULT_PROP_MAP/DEFAULT_STANDARD_KEYS)
    property_map: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PROP_MAP))
    standard_keys: list[str] = field(default_factory=lambda: list(DEFAULT_STANDARD_KEYS))

    # Sync protected paths (top-level names and specific sub-paths to preserve in sync target)
    sync_protected_top: frozenset[str] = field(
        default_factory=lambda: frozenset(_DEFAULT_SYNC_PROTECTED_TOP))
    sync_protected_paths: frozenset[str] = field(
        default_factory=lambda: frozenset(_DEFAULT_SYNC_PROTECTED_PATHS))

    # Specification: custom colors, element shapes, tags
    spec_colors: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_SPEC_COLORS))
    spec_shapes: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_SPEC_SHAPES))
    spec_tags: list[str] = field(
        default_factory=lambda: list(_DEFAULT_SPEC_TAGS))

    # CLI flags
    strict: bool = False
    verbose: bool = False
    dry_run: bool = False


def load_config(config_path: Path | None) -> ConvertConfig:
    """Load configuration from a YAML file.

    When *config_path* is ``None``, auto-detects ``.archi2likec4.yaml`` in the
    current directory.  When an explicit path is given but does not exist,
    raises :class:`FileNotFoundError`.
    """
    config = ConvertConfig()
    explicit = config_path is not None
    if config_path is None:
        # Auto-detect .archi2likec4.yaml in current directory
        auto = Path('.archi2likec4.yaml')
        if auto.exists():
            config_path = auto
    if config_path is not None:
        if not config_path.exists():
            if explicit:
                raise FileNotFoundError(
                    f'Config file not found: {config_path}')
            return config  # auto-detect miss — return defaults
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as err:
            raise ConfigError(
                f'Config file {config_path} requires PyYAML: pip install pyyaml') from err
        with open(config_path, encoding='utf-8') as fh:
            try:
                data = yaml.safe_load(fh) or {}
            except yaml.YAMLError as err:
                raise ConfigError(
                    f'Config file {config_path}: YAML parse error: {err}') from err
        if not isinstance(data, dict):
            raise ConfigError(
                f'Config file {config_path}: expected YAML mapping at root, '
                f'got {type(data).__name__}')
        _apply_yaml(config, data)
    return config


_KNOWN_YAML_KEYS: set[str] = {
    'promote_children', 'promote_warn_threshold',
    'domain_renames', 'extra_domain_patterns',
    'quality_gates',
    'audit_suppress', 'audit_suppress_incidents',
    'domain_overrides', 'subdomain_overrides', 'reviewed_systems',
    'language', 'deployment_env', 'extra_view_patterns', 'strict', 'sync_target',
    'property_map', 'standard_keys',
    'sync_protected_top', 'sync_protected_paths',
    'spec_colors', 'spec_shapes', 'spec_tags',
}


def _apply_yaml(config: ConvertConfig, data: dict) -> None:
    """Merge *data* from YAML into *config*, overriding only supplied keys."""
    unknown = set(data.keys()) - _KNOWN_YAML_KEYS
    if unknown:
        logger.warning('Unknown config keys (ignored): %s', ', '.join(sorted(unknown)))
    if 'promote_children' in data:
        if not isinstance(data['promote_children'], dict):
            raise ConfigError(
                f"promote_children: expected mapping, got {type(data['promote_children']).__name__}")
        for k, v in data['promote_children'].items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ConfigError(
                    f"promote_children['{k}']: key and value must be strings, "
                    f"got key={type(k).__name__}, value={type(v).__name__}")
            if not _VALID_C4_ID.match(v):
                raise ConfigError(
                    f"promote_children['{k}']: invalid C4 identifier "
                    f"'{v}' (must match {_VALID_C4_ID.pattern})")
        config.promote_children = data['promote_children']
    if 'promote_warn_threshold' in data:
        try:
            val = int(data['promote_warn_threshold'])
        except (ValueError, TypeError) as exc:
            raise ConfigError(
                f"promote_warn_threshold: expected integer, got {data['promote_warn_threshold']!r}"
            ) from exc
        if val < 0:
            raise ConfigError(f"promote_warn_threshold: must be non-negative, got {val}")
        config.promote_warn_threshold = val
    if 'domain_renames' in data:
        if not isinstance(data['domain_renames'], dict):
            raise ConfigError(
                f"domain_renames: expected mapping, got {type(data['domain_renames']).__name__}")
        renames: dict[str, tuple[str, str]] = {}
        for k, v in data['domain_renames'].items():
            if not isinstance(v, (list, tuple)) or len(v) != 2:
                raise ConfigError(
                    f"domain_renames['{k}']: expected [new_id, 'Display Name'], "
                    f"got {v!r}")
            if not isinstance(v[0], str) or not isinstance(v[1], str):
                raise ConfigError(
                    f"domain_renames['{k}']: values must be strings, got {v!r}")
            if not _VALID_C4_ID.match(v[0]):
                raise ConfigError(
                    f"domain_renames['{k}']: invalid C4 identifier "
                    f"'{v[0]}' (must match {_VALID_C4_ID.pattern})")
            renames[k] = tuple(v)
        config.domain_renames = renames
    if 'extra_domain_patterns' in data:
        if not isinstance(data['extra_domain_patterns'], list):
            raise ConfigError(
                f"extra_domain_patterns: expected list, got {type(data['extra_domain_patterns']).__name__}")
        validated: list[dict[str, Any]] = []
        for i, entry in enumerate(data['extra_domain_patterns']):
            if not isinstance(entry, dict):
                raise ConfigError(
                    f"extra_domain_patterns[{i}]: expected mapping, got {type(entry).__name__}")
            for key in ('c4_id', 'name', 'patterns'):
                if key not in entry:
                    raise ConfigError(
                        f"extra_domain_patterns[{i}]: missing required key '{key}'")
            if not isinstance(entry['c4_id'], str):
                raise ConfigError(
                    f"extra_domain_patterns[{i}]['c4_id']: expected string, "
                    f"got {type(entry['c4_id']).__name__}")
            if not _VALID_C4_ID.match(entry['c4_id']):
                raise ConfigError(
                    f"extra_domain_patterns[{i}]['c4_id']: invalid C4 identifier "
                    f"'{entry['c4_id']}' (must match {_VALID_C4_ID.pattern})")
            if not isinstance(entry['name'], str):
                raise ConfigError(
                    f"extra_domain_patterns[{i}]['name']: expected string, "
                    f"got {type(entry['name']).__name__}")
            if not isinstance(entry['patterns'], list):
                raise ConfigError(
                    f"extra_domain_patterns[{i}]['patterns']: expected list, "
                    f"got {type(entry['patterns']).__name__}")
            for j, pat in enumerate(entry['patterns']):
                if not isinstance(pat, str):
                    raise ConfigError(
                        f"extra_domain_patterns[{i}]['patterns'][{j}]: expected string, "
                        f"got {type(pat).__name__}")
            validated.append(entry)
        config.extra_domain_patterns = validated

    # Quality gates (nested dict)
    gates = data.get('quality_gates')
    if isinstance(gates, dict):
        if 'max_unresolved_ratio' in gates:
            try:
                ratio = float(gates['max_unresolved_ratio'])
            except (ValueError, TypeError) as err:
                raise ConfigError(
                    f"quality_gates.max_unresolved_ratio: expected float, "
                    f"got {gates['max_unresolved_ratio']!r}") from err
            if not 0 <= ratio <= 1:
                raise ConfigError(
                    f"quality_gates.max_unresolved_ratio: must be between 0 and 1, got {ratio}")
            config.max_unresolved_ratio = ratio
        if 'max_orphan_functions_warn' in gates:
            try:
                val = int(gates['max_orphan_functions_warn'])
            except (ValueError, TypeError) as err:
                raise ConfigError(
                    f"quality_gates.max_orphan_functions_warn: expected integer, "
                    f"got {gates['max_orphan_functions_warn']!r}") from err
            if val < 0:
                raise ConfigError(f"quality_gates.max_orphan_functions_warn: must be non-negative, got {val}")
            config.max_orphan_functions_warn = val
        if 'max_unassigned_systems_warn' in gates:
            try:
                val = int(gates['max_unassigned_systems_warn'])
            except (ValueError, TypeError) as err:
                raise ConfigError(
                    f"quality_gates.max_unassigned_systems_warn: expected integer, "
                    f"got {gates['max_unassigned_systems_warn']!r}") from err
            if val < 0:
                raise ConfigError(f"quality_gates.max_unassigned_systems_warn: must be non-negative, got {val}")
            config.max_unassigned_systems_warn = val

    if 'audit_suppress' in data:
        if not isinstance(data['audit_suppress'], list):
            raise ConfigError(
                f"audit_suppress: expected list, got {type(data['audit_suppress']).__name__}")
        for item in data['audit_suppress']:
            if not isinstance(item, str):
                raise ConfigError(
                    f"audit_suppress: all items must be strings, got {type(item).__name__}: {item!r}")
        config.audit_suppress = list(data['audit_suppress'])
    if 'audit_suppress_incidents' in data:
        if not isinstance(data['audit_suppress_incidents'], list):
            raise ConfigError(
                f"audit_suppress_incidents: expected list, "
                f"got {type(data['audit_suppress_incidents']).__name__}")
        for item in data['audit_suppress_incidents']:
            if not isinstance(item, str):
                raise ConfigError(
                    f"audit_suppress_incidents: all items must be strings, "
                    f"got {type(item).__name__}: {item!r}")
        config.audit_suppress_incidents = list(data['audit_suppress_incidents'])

    if 'domain_overrides' in data:
        if not isinstance(data['domain_overrides'], dict):
            raise ConfigError(
                f"domain_overrides: expected mapping, got {type(data['domain_overrides']).__name__}")
        overrides: dict[str, str] = {}
        for k, v in data['domain_overrides'].items():
            id_val = str(v)
            if not _VALID_C4_ID.match(id_val):
                raise ConfigError(
                    f"domain_overrides['{k}']: invalid C4 identifier "
                    f"'{id_val}' (must match {_VALID_C4_ID.pattern})")
            overrides[str(k)] = id_val
        config.domain_overrides = overrides
    if 'subdomain_overrides' in data:
        if not isinstance(data['subdomain_overrides'], dict):
            raise ConfigError(
                f"subdomain_overrides: expected mapping, got {type(data['subdomain_overrides']).__name__}")
        sd_overrides: dict[str, str] = {}
        for k, v in data['subdomain_overrides'].items():
            id_val = str(v)
            if not _VALID_C4_ID.match(id_val):
                raise ConfigError(
                    f"subdomain_overrides['{k}']: invalid C4 identifier "
                    f"'{id_val}' (must match {_VALID_C4_ID.pattern})")
            sd_overrides[str(k)] = id_val
        config.subdomain_overrides = sd_overrides
    if 'reviewed_systems' in data:
        if not isinstance(data['reviewed_systems'], list):
            raise ConfigError(
                f"reviewed_systems: expected list, got {type(data['reviewed_systems']).__name__}")
        for item in data['reviewed_systems']:
            if not isinstance(item, str):
                raise ConfigError(
                    f"reviewed_systems: all items must be strings, got {type(item).__name__}: {item!r}")
        config.reviewed_systems = list(data['reviewed_systems'])

    if 'language' in data:
        lang = str(data['language']).lower()
        if lang not in ('ru', 'en'):
            raise ConfigError(
                f"language: expected 'ru' or 'en', got '{data['language']}'")
        config.language = lang

    if 'deployment_env' in data:
        env_val = str(data['deployment_env']).strip()
        if not env_val:
            raise ConfigError("deployment_env: must not be empty")
        config.deployment_env = env_val

    if 'extra_view_patterns' in data:
        val = data['extra_view_patterns']
        if not isinstance(val, list):
            raise ConfigError(
                f"extra_view_patterns: expected list, got {type(val).__name__}")
        validated_vp: list[dict[str, str]] = []
        for i, entry in enumerate(val):
            if not isinstance(entry, dict):
                raise ConfigError(
                    f"extra_view_patterns[{i}]: expected mapping, got {type(entry).__name__}")
            for key in ('pattern', 'view_type'):
                if key not in entry:
                    raise ConfigError(
                        f"extra_view_patterns[{i}]: missing required key '{key}'")
                if not isinstance(entry[key], str):
                    raise ConfigError(
                        f"extra_view_patterns[{i}]['{key}']: expected string, "
                        f"got {type(entry[key]).__name__}")
            if entry['view_type'] not in ('functional', 'integration', 'deployment'):
                raise ConfigError(
                    f"extra_view_patterns[{i}]['view_type']: must be 'functional', "
                    f"'integration', or 'deployment', got '{entry['view_type']}'")
            try:
                re.compile(entry['pattern'])
            except re.error as err:
                raise ConfigError(
                    f"extra_view_patterns[{i}]['pattern']: invalid regex: {err}") from err
            validated_vp.append({'pattern': entry['pattern'], 'view_type': entry['view_type']})
        config.extra_view_patterns = validated_vp

    if 'strict' in data:
        val = data['strict']
        if isinstance(val, bool):
            config.strict = val
        elif isinstance(val, str):
            if val.lower() in ('true', '1', 'yes'):
                config.strict = True
            elif val.lower() in ('false', '0', 'no'):
                config.strict = False
            else:
                raise ConfigError(
                    f"strict: expected bool or 'true'/'false', got '{val}'")
        else:
            raise ConfigError(
                f"strict: expected bool or string, got {type(val).__name__}")

    if 'sync_target' in data:
        val = data['sync_target']
        if val is None:
            config.sync_target = None
        else:
            if not isinstance(val, str):
                raise ConfigError(
                    f"sync_target: expected string path, got {type(val).__name__}")
            target = Path(val).expanduser().resolve()
            if not target.exists():
                raise ConfigError(
                    f"sync_target: directory does not exist: {target}")
            if not target.is_dir():
                raise ConfigError(
                    f"sync_target: path is not a directory: {target}")
            config.sync_target = target

    if 'property_map' in data:
        val = data['property_map']
        if not isinstance(val, dict):
            raise ConfigError(
                f"property_map: expected mapping, got {type(val).__name__}")
        for k, v in val.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ConfigError(
                    f"property_map: keys and values must be strings, got {k!r}: {v!r}")
        config.property_map = {**config.property_map, **val}

    if 'standard_keys' in data:
        val = data['standard_keys']
        if not isinstance(val, list):
            raise ConfigError(
                f"standard_keys: expected list, got {type(val).__name__}")
        for item in val:
            if not isinstance(item, str):
                raise ConfigError(
                    f"standard_keys: all items must be strings, got {type(item).__name__}: {item!r}")
        config.standard_keys = list(val)

    if 'spec_colors' in data:
        val = data['spec_colors']
        if not isinstance(val, dict):
            raise ConfigError(
                f"spec_colors: expected mapping, got {type(val).__name__}")
        for k, v in val.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ConfigError(
                    f"spec_colors: keys and values must be strings, got {k!r}: {v!r}")
        config.spec_colors = {**config.spec_colors, **val}

    if 'spec_shapes' in data:
        val = data['spec_shapes']
        if not isinstance(val, dict):
            raise ConfigError(
                f"spec_shapes: expected mapping, got {type(val).__name__}")
        for k, v in val.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ConfigError(
                    f"spec_shapes: keys and values must be strings, got {k!r}: {v!r}")
        config.spec_shapes = {**config.spec_shapes, **val}

    if 'spec_tags' in data:
        val = data['spec_tags']
        if not isinstance(val, list):
            raise ConfigError(
                f"spec_tags: expected list, got {type(val).__name__}")
        for item in val:
            if not isinstance(item, str):
                raise ConfigError(
                    f"spec_tags: all items must be strings, got {type(item).__name__}: {item!r}")
        config.spec_tags = list(val)

    if 'sync_protected_top' in data:
        val = data['sync_protected_top']
        if not isinstance(val, list):
            raise ConfigError(
                f"sync_protected_top: expected list, got {type(val).__name__}")
        for item in val:
            if not isinstance(item, str):
                raise ConfigError(
                    f"sync_protected_top: all items must be strings, got {type(item).__name__}: {item!r}")
        config.sync_protected_top = frozenset(s.rstrip('/') for s in val)

    if 'sync_protected_paths' in data:
        val = data['sync_protected_paths']
        if not isinstance(val, list):
            raise ConfigError(
                f"sync_protected_paths: expected list, got {type(val).__name__}")
        for item in val:
            if not isinstance(item, str):
                raise ConfigError(
                    f"sync_protected_paths: all items must be strings, "
                    f"got {type(item).__name__}: {item!r}")
        config.sync_protected_paths = frozenset(s.rstrip('/') for s in val)


def save_suppress(
    config_path: Path,
    suppress_names: list[str],
    suppress_incidents: list[str],
) -> None:
    """Update audit_suppress and audit_suppress_incidents in YAML config file.

    Creates the file if it does not exist.  Preserves all other keys.
    """
    import yaml  # type: ignore[import-untyped]

    data: dict = {}
    if config_path.exists():
        with open(config_path, encoding='utf-8') as fh:
            raw = yaml.safe_load(fh)
            data = raw if isinstance(raw, dict) else {}

    if suppress_names:
        data['audit_suppress'] = sorted(set(suppress_names))
    else:
        data.pop('audit_suppress', None)

    if suppress_incidents:
        data['audit_suppress_incidents'] = sorted(set(suppress_incidents))
    else:
        data.pop('audit_suppress_incidents', None)

    with open(config_path, 'w', encoding='utf-8') as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


def update_config_field(
    config_path: Path,
    field_name: str,
    value: dict | list | str | int | float | bool | None,
) -> None:
    """Update a single field in YAML config file.

    Creates the file if it does not exist.  Preserves all other keys.
    If *value* is an empty dict/list or ``None``, removes the key.
    """
    import yaml  # type: ignore[import-untyped]

    data: dict = {}
    if config_path.exists():
        with open(config_path, encoding='utf-8') as fh:
            raw = yaml.safe_load(fh)
            data = raw if isinstance(raw, dict) else {}

    if value is None or value == {} or value == []:
        data.pop(field_name, None)
    else:
        data[field_name] = value

    with open(config_path, 'w', encoding='utf-8') as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
