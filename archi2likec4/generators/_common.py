"""Shared helpers for generators."""

from __future__ import annotations

_MAX_DESC_LEN = 500


def truncate_desc(desc: str, max_len: int = _MAX_DESC_LEN) -> str:
    """Truncate description to *max_len* characters, appending '...' if cut."""
    if len(desc) > max_len:
        return desc[:max_len - 3] + '...'
    return desc


def render_metadata(
    lines: list[str],
    archi_id: str,
    pad: str,
    extra: dict[str, str] | None = None,
) -> None:
    """Append a ``metadata { archi_id '...' }`` block to *lines*.

    Values in *extra* must already be escaped by the caller.
    """
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{archi_id}'")
    if extra:
        for key, value in extra.items():
            lines.append(f"{pad}    {key} '{value}'")
    lines.append(f'{pad}  }}')
