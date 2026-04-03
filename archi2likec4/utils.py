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


_VALID_C4_ID = re.compile(r'^[a-z][a-z0-9_]*$')


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
    text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
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


def system_path_from_c4(
    path: str,
    sys_subdomain: dict[str, str] | None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
) -> str:
    """Extract the domain-qualified system path from a full c4 element path.

    Handles both 2-part (domain.system) and 3-part (domain.subdomain.system)
    paths as well as deeper paths (subsystems, functions).  When sys_subdomain
    is provided it is used to detect whether the second segment is a subdomain
    rather than the system itself.

    ``sys_ids`` is the set of all known system c4_ids.  When provided, the
    3-part path is only returned if parts[2] is a known system, preventing a
    false match when parts[2] is a subsystem whose archi_id coincidentally
    equals a system that has parts[1] as its subdomain.

    ``sys_domain`` maps system c4_id → domain name.  When provided, the
    3-part path is only returned if parts[2] belongs to the same domain as
    parts[0], preventing a false match when a same-named system exists in a
    different domain.
    """
    parts = path.split('.')
    if (
        sys_subdomain
        and len(parts) >= 3
        and sys_subdomain.get(parts[2]) == parts[1]
        and (sys_ids is None or parts[2] in sys_ids)
        and (sys_domain is None or sys_domain.get(parts[2]) == parts[0])
    ):
        return f'{parts[0]}.{parts[1]}.{parts[2]}'
    if len(parts) >= 2:
        return f'{parts[0]}.{parts[1]}'
    return path


def extract_system_id(
    app_path: str,
    sys_subdomain: dict[str, str] | None = None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
) -> str:
    """Extract the system c4_id from a full app path, sanitized for tag use.

    Uses :func:`system_path_from_c4` to handle subdomain paths correctly,
    then returns the last segment as the system identifier with hyphens
    replaced by underscores (LikeC4 tags don't support hyphens).
    """
    raw = system_path_from_c4(app_path, sys_subdomain, sys_ids, sys_domain).rsplit('.', 1)[-1]
    return raw.replace('-', '_')


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
