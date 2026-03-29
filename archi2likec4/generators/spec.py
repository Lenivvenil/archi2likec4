"""Generate LikeC4 specification block."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archi2likec4.config import ConvertConfig

# Element-kind → default color name (used when generating spec).
_DEFAULT_ELEMENT_COLORS: dict[str, str] = {
    'domain': 'amber',
    'subdomain': 'secondary',
    'system': 'archi-app',
    'subsystem': 'archi-app-light',
    'appFunction': 'archi-app-light',
    'dataEntity': 'archi-data',
    'dataStore': 'archi-store',
    'infraNode': 'archi-tech',
    'infraSoftware': 'archi-tech-light',
    'infraZone': 'archi-tech',
    'infraLocation': 'archi-tech',
}

# Deployment-node kinds (use `deploymentNode` keyword instead of `element`).
_DEPLOYMENT_KINDS: frozenset[str] = frozenset({
    'infraNode', 'infraSoftware', 'infraZone', 'infraLocation',
})

# Extra border styles per element kind.
_BORDER_OVERRIDES: dict[str, str] = {
    'infraZone': 'dotted',
    'infraLocation': 'dashed',
}

# Element kinds in output order.
_ELEMENT_ORDER: list[str] = [
    'domain', 'subdomain',
    'system', 'subsystem', 'appFunction',
    'dataEntity', 'dataStore',
    'infraNode', 'infraSoftware', 'infraZone', 'infraLocation',
]


def generate_spec(config: ConvertConfig | None = None) -> str:
    """Build the LikeC4 ``specification { … }`` block.

    When *config* is supplied, ``spec_colors``, ``spec_shapes``, and
    ``spec_tags`` are read from it; otherwise built-in defaults are used.
    """
    from archi2likec4.config import (
        _DEFAULT_SPEC_COLORS,
        _DEFAULT_SPEC_SHAPES,
        _DEFAULT_SPEC_TAGS,
    )
    if config is not None:
        colors = {**_DEFAULT_SPEC_COLORS, **config.spec_colors}
        shapes = {**_DEFAULT_SPEC_SHAPES, **config.spec_shapes}
        tags = list(dict.fromkeys(list(_DEFAULT_SPEC_TAGS) + list(config.spec_tags)))
    else:
        colors = _DEFAULT_SPEC_COLORS
        shapes = _DEFAULT_SPEC_SHAPES
        tags = _DEFAULT_SPEC_TAGS

    lines: list[str] = ['specification {', '']

    # ── Custom colors (application layer) ────────────────────────
    app_colors = {k: v for k, v in colors.items() if not k.startswith('archi-tech')}
    if app_colors:
        lines.append('  // ── Colors ──────────────────────────────────────────────')
        for name, hex_val in app_colors.items():
            lines.append(f'  color {name} {hex_val}')
        lines.append('')

    # ── Element kinds ────────────────────────────────────────────
    sections: list[tuple[str, list[str]]] = [
        ('Business domains', ['domain', 'subdomain']),
        ('Application landscape', ['system', 'subsystem', 'appFunction']),
        ('Data layer', ['dataEntity', 'dataStore']),
    ]
    for header, kinds in sections:
        lines.append(f'  // ── {header} {"─" * max(1, 50 - len(header))}')
        for kind in kinds:
            shape = shapes.get(kind, 'rectangle')
            color = _DEFAULT_ELEMENT_COLORS.get(kind, 'muted')
            lines.append(f'  element {kind} {{')
            lines.append('    style {')
            lines.append(f'      shape {shape}')
            lines.append(f'      color {color}')
            lines.append('    }')
            lines.append('  }')
            lines.append('')

    # ── Infrastructure / Deployment ──────────────────────────────
    infra_colors = {k: v for k, v in colors.items() if k.startswith('archi-tech')}
    if infra_colors:
        lines.append('  // ── Infrastructure / Deployment ──────────────────────')
        for name, hex_val in infra_colors.items():
            lines.append(f'  color {name} {hex_val}')
        lines.append('')

    infra_kinds = [k for k in _ELEMENT_ORDER if k in _DEPLOYMENT_KINDS]
    for kind in infra_kinds:
        shape = shapes.get(kind, 'rectangle')
        color = _DEFAULT_ELEMENT_COLORS.get(kind, 'muted')
        border = _BORDER_OVERRIDES.get(kind)
        lines.append(f'  deploymentNode {kind} {{')
        lines.append('    style {')
        lines.append(f'      shape {shape}')
        lines.append(f'      color {color}')
        if border:
            lines.append(f'      border {border}')
        lines.append('    }')
        lines.append('  }')
        lines.append('')

    # ── Relationship kinds ───────────────────────────────────────
    lines.append('  // ── Relationship kinds ─────────────────────────────────')
    lines.append('  relationship persists {')
    lines.append('    color archi-store')
    lines.append('    line dashed')
    lines.append('  }')
    lines.append('')

    # ── Tags ─────────────────────────────────────────────────────
    lines.append('  // ── Tags ───────────────────────────────────────────────')
    for tag in tags:
        lines.append(f'  tag {tag}')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
