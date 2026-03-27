"""Generate data entities .c4 file."""

from __future__ import annotations

from ..models import DataAccess, DataEntity
from ..utils import escape_str
from ._common import render_metadata, truncate_desc

_MAX_ENTITY_DESC_LEN = 300


def generate_entities(entities: list[DataEntity], data_access: list[DataAccess]) -> str:
    """Generate entities.c4: dataEntity elements + access relationships."""
    lines = [
        '// ── Data Entities ───────────────────────────────────────',
        '//',
        '// Migrated from ArchiMate DataObject as-is.',
        '// Quality is low (Kafka topics, internal structures, etc.).',
        '//',
        '// TODO: Canonical data model (Customer, Account, Loan, etc.)',
        '//       to be designed separately. These migrated entities',
        '//       preserve the original ArchiMate relationships and',
        '//       serve as an inventory for future data governance.',
        '//',
        '// Target pattern (when dataStore is added at container level):',
        '//   dataStore -[persists]-> dataEntity',
        '//',
        '// Current: domain.system -> dataEntity (migrated AccessRelationship)',
        '//',
        '',
        'model {',
        '',
    ]

    if not entities:
        lines.append('  // No data entities found')
    else:
        for entity in entities:
            title = escape_str(entity.name)
            lines.append(f"  {entity.c4_id} = dataEntity '{title}' {{")
            lines.append('    #entity')
            if entity.documentation:
                desc = truncate_desc(escape_str(entity.documentation), max_len=_MAX_ENTITY_DESC_LEN)
                lines.append(f"    description '{desc}'")
            render_metadata(lines, entity.archi_id, '  ')
            lines.append("  }")
            lines.append('')

    # Access relationships (migrated from ArchiMate AccessRelationship)
    if data_access:
        lines.append('  // ── System → DataEntity access (migrated from ArchiMate) ──')
        lines.append('  // These represent which systems work with which data entities.')
        lines.append('  // To be replaced by: dataStore -[persists]-> dataEntity')
        lines.append('  // when container/store level is modeled.')
        lines.append('')
        for da in data_access:
            if da.name:
                label = escape_str(da.name)
                lines.append(f"  {da.system_path} -> {da.entity_id} '{label}'")
            else:
                lines.append(f"  {da.system_path} -> {da.entity_id}")
        lines.append('')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
