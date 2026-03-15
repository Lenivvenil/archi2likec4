"""Utility functions: transliteration, ID generation, string escaping, metadata."""

import re

from .models import (
    _CYRILLIC_MAP,
    _PROP_MAP,
    _RESERVED,
    _STANDARD_KEYS,
    AppComponent,
    DeploymentNode,
)


def transliterate(text: str) -> str:
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in _CYRILLIC_MAP:
            mapped = _CYRILLIC_MAP[lower]
            result.append(mapped.upper() if ch.isupper() else mapped)
        else:
            result.append(ch)
    return ''.join(result)


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
    if text in _RESERVED:
        text = text + '_el'
    return text


def escape_str(text: str) -> str:
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


def build_metadata(ac: AppComponent) -> dict[str, str]:
    raw: dict[str, str] = {}
    for archi_key, value in ac.properties.items():
        c4_key = _PROP_MAP.get(archi_key)
        if c4_key:
            raw[c4_key] = value
    result: dict[str, str] = {}
    for key in _STANDARD_KEYS:
        if key == 'full_name':
            result[key] = raw.get(key, ac.name)
        else:
            result[key] = raw.get(key, 'TBD')
    return result
