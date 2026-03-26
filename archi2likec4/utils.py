"""Utility functions: transliteration, ID generation, string escaping, metadata."""

import re

from .models import (
    CYRILLIC_MAP,
    DEFAULT_PROP_MAP,
    DEFAULT_STANDARD_KEYS,
    RESERVED,
    AppComponent,
    DeploymentNode,
)


def transliterate(text: str) -> str:
    """Transliterate a Cyrillic string to Latin characters."""
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in CYRILLIC_MAP:
            mapped = CYRILLIC_MAP[lower]
            result.append(mapped.upper() if ch.isupper() else mapped)
        else:
            result.append(ch)
    return ''.join(result)


_VALID_C4_ID = re.compile(r'^[a-z][a-z0-9_-]*$')


def validate_c4_id(value: str) -> str:
    """Validate that *value* is a well-formed LikeC4 identifier.

    Raises ValueError if the identifier contains characters that would produce
    invalid LikeC4 syntax when interpolated into .c4 output.
    """
    if not _VALID_C4_ID.match(value):
        raise ValueError(f'Invalid LikeC4 identifier: {value!r}')
    return value


def make_id(name: str, prefix: str = '') -> str:
    """Convert a human name to a valid LikeC4 identifier."""
    text = transliterate(name.strip())
    text = re.sub(r'[^a-zA-Z0-9_-]', '_', text)
    text = text.lower()
    text = re.sub(r'_+', '_', text)
    text = text.strip('_')
    if not text:
        text = 'unnamed'
    if prefix:
        text = f'{prefix}_{text}'
    if text[0].isdigit():
        text = 'n' + text
    if text in RESERVED:
        text = text + '_el'
    assert _VALID_C4_ID.match(text), f'make_id produced invalid identifier: {text!r}'
    return text


def escape_str(text: str) -> str:
    """Escape a string for safe inclusion in LikeC4 output."""
    text = text.replace('&#xD;', '').replace('&#xA;', '')
    text = text.replace('\\', '\\\\')
    text = text.replace("'", "\\'")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def make_unique_id(base_id: str, used_ids: set[str]) -> str:
    """Return *base_id* if unused, otherwise append _2, _3, … until unique."""
    if base_id not in used_ids:
        return base_id
    suffix = 2
    while f'{base_id}_{suffix}' in used_ids:
        suffix += 1
    return f'{base_id}_{suffix}'


def flatten_deployment_nodes(nodes: list[DeploymentNode]) -> list[DeploymentNode]:
    """Recursively flatten a tree of DeploymentNodes into a flat list."""
    result: list[DeploymentNode] = []
    for node in nodes:
        result.append(node)
        result.extend(flatten_deployment_nodes(node.children))
    return result


def build_metadata(
    ac: AppComponent,
    prop_map: dict[str, str] | None = None,
    standard_keys: list[str] | None = None,
) -> dict[str, str]:
    """Build metadata dict from ArchiMate properties."""
    _pm = prop_map if prop_map is not None else DEFAULT_PROP_MAP
    _sk = standard_keys if standard_keys is not None else DEFAULT_STANDARD_KEYS
    raw: dict[str, str] = {}
    for archi_key, value in ac.properties.items():
        c4_key = _pm.get(archi_key)
        if c4_key:
            raw[c4_key] = value
    result: dict[str, str] = {}
    for key in _sk:
        if key == 'full_name':
            result[key] = raw.get(key, ac.name)
        else:
            result[key] = raw.get(key, 'TBD')
    return result
