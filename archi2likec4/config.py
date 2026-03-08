"""Configuration: YAML file → dataclass, CLI defaults."""

from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    DOMAIN_RENAMES,
    EXTRA_DOMAIN_PATTERNS,
    PROMOTE_CHILDREN,
    PROMOTE_WARN_THRESHOLD,
)


@dataclass
class ConvertConfig:
    """All tuneable parameters for the converter."""

    model_root: Path = field(default_factory=lambda: Path('architectural_repository/model'))
    output_dir: Path = field(default_factory=lambda: Path('output'))

    # Subsystem promotion
    promote_children: dict[str, str] = field(
        default_factory=lambda: dict(PROMOTE_CHILDREN))
    promote_warn_threshold: int = PROMOTE_WARN_THRESHOLD

    # Domain configuration
    domain_renames: dict[str, tuple[str, str]] = field(
        default_factory=lambda: dict(DOMAIN_RENAMES))
    extra_domain_patterns: list[dict] = field(
        default_factory=lambda: list(EXTRA_DOMAIN_PATTERNS))

    # Quality gates
    max_unresolved_ratio: float = 0.5
    max_orphan_functions_warn: int = 5
    max_unassigned_systems_warn: int = 20

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
        except ImportError:
            raise SystemExit(
                f'Config file {config_path} requires PyYAML: pip install pyyaml')
        with open(config_path, 'r', encoding='utf-8') as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(
                f'Config file {config_path}: expected YAML mapping at root, '
                f'got {type(data).__name__}')
        _apply_yaml(config, data)
    return config


def _apply_yaml(config: ConvertConfig, data: dict) -> None:
    """Merge *data* from YAML into *config*, overriding only supplied keys."""
    if 'promote_children' in data and isinstance(data['promote_children'], dict):
        config.promote_children = data['promote_children']
    if 'promote_warn_threshold' in data:
        config.promote_warn_threshold = int(data['promote_warn_threshold'])
    if 'domain_renames' in data and isinstance(data['domain_renames'], dict):
        renames: dict[str, tuple[str, str]] = {}
        for k, v in data['domain_renames'].items():
            if not isinstance(v, (list, tuple)) or len(v) != 2:
                raise ValueError(
                    f"domain_renames['{k}']: expected [new_id, 'Display Name'], "
                    f"got {v!r}")
            renames[k] = tuple(v)
        config.domain_renames = renames
    if 'extra_domain_patterns' in data and isinstance(data['extra_domain_patterns'], list):
        config.extra_domain_patterns = data['extra_domain_patterns']

    # Quality gates (nested dict)
    gates = data.get('quality_gates')
    if isinstance(gates, dict):
        if 'max_unresolved_ratio' in gates:
            config.max_unresolved_ratio = float(gates['max_unresolved_ratio'])
        if 'max_orphan_functions_warn' in gates:
            config.max_orphan_functions_warn = int(gates['max_orphan_functions_warn'])
        if 'max_unassigned_systems_warn' in gates:
            config.max_unassigned_systems_warn = int(gates['max_unassigned_systems_warn'])

    if 'strict' in data:
        config.strict = bool(data['strict'])
