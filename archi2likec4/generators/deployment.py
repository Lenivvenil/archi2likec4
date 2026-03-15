"""Generate deployment topology .c4 files."""

from __future__ import annotations

from ..models import DeploymentNode
from ..utils import escape_str

_MAX_DESC_LEN = 500


def _render_deployment_node(node: DeploymentNode, lines: list[str], indent: int) -> None:
    """Recursively render a DeploymentNode and its children."""
    pad = ' ' * indent
    title = escape_str(node.name)
    lines.append(f"{pad}{node.c4_id} = {node.kind} '{title}' {{")
    if node.documentation:
        desc = escape_str(node.documentation)
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
        lines.append(f"{pad}  description '{desc}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{node.archi_id}'")
    lines.append(f"{pad}    tech_type '{node.tech_type}'")
    lines.append(f'{pad}  }}')
    for child in sorted(node.children, key=lambda c: c.name):
        lines.append('')
        _render_deployment_node(child, lines, indent + 2)
    lines.append(f'{pad}}}')


def generate_deployment_c4(nodes: list[DeploymentNode]) -> str:
    """Generate deployment/topology.c4 with infrastructure nodes and containers."""
    lines = [
        '// ── Deployment Topology ──────────────────────────────────',
        'model {',
        '',
    ]
    for node in sorted(nodes, key=lambda n: n.name):
        _render_deployment_node(node, lines, indent=2)
        lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_deployment_mapping_c4(mapping: list[tuple[str, str]]) -> str:
    """Generate deployment/mapping.c4 with app→infrastructure relationships."""
    lines = [
        '// ── Deployment Mapping (App → Infrastructure) ────────────',
        'model {',
        '',
    ]
    for app_path, node_id in sorted(mapping):
        lines.append(f'  {app_path} -[deployedOn]-> {node_id}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_datastore_mapping_c4(links: list[tuple[str, str]]) -> str:
    """Generate deployment/datastore-mapping.c4 with dataStore→dataEntity relationships."""
    lines = [
        '// ── DataStore → DataEntity (persistence layer) ─────────────',
        'model {',
        '',
    ]
    for store_path, entity_id in sorted(links):
        lines.append(f'  {store_path} -[persists]-> {entity_id}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_deployment_view() -> str:
    """Generate views/deployment-architecture.c4."""
    return """\
views {

  view deployment_architecture {
    title 'Deployment Architecture'

    include
      element.kind = infraLocation,
      element.kind = infraZone,
      element.kind = infraNode,
      element.kind = infraSoftware,
      element.kind = dataStore
  }

}
"""
