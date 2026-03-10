"""Utility functions: transliteration, ID generation, string escaping, metadata."""

import re

from .models import (
    AppComponent,
    _CYRILLIC_MAP,
    _PROP_MAP,
    _RESERVED,
    _STANDARD_KEYS,
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


def sanitize_path_segment(segment: str) -> str:
    """Sanitize a string for safe use as a filesystem path segment.

    Strips path separators, parent-directory references, and null bytes.
    Returns a safe slug or 'invalid' if nothing remains.
    """
    # Remove null bytes and strip whitespace
    segment = segment.replace('\x00', '').strip()
    # Collapse path separators and parent refs
    segment = segment.replace('/', '_').replace('\\', '_')
    segment = segment.replace('..', '_')
    # Remove leading dots (hidden files)
    segment = segment.lstrip('.')
    # Strip residual underscores/dots left after sanitization
    segment = segment.strip('_.')
    if not segment:
        return 'invalid'
    return segment


def escape_str(text: str) -> str:
    text = text.replace('&#xD;', '').replace('&#xA;', '')
    text = text.replace('\\', '\\\\')
    text = text.replace("'", "\\'")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
