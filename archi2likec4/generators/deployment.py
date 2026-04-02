"""Generate deployment topology .c4 files."""

from __future__ import annotations

from ..models import DeploymentNode
from ..utils import escape_str
from ._common import render_metadata, truncate_desc


def _render_deployment_node(
    node: DeploymentNode,
    lines: list[str],
    indent: int,
    current_path: str,
    instances: dict[str, list[str]],
) -> None:
    """Recursively render a DeploymentNode and its children.

    Appends ``instanceOf <app_path>`` for each application mapped to this node
    via the deployment_map passed to :func:`generate_deployment_c4`.
    """
    pad = ' ' * indent
    title = escape_str(node.name)
    node_instances = instances.get(current_path, [])
    # Nodes with instanceOf are deployment targets (hosts) — use 'host' kind
    effective_kind = 'host' if node_instances else node.kind
    lines.append(f"{pad}{node.c4_id} = {effective_kind} '{title}' {{")
    # System tags FIRST (LikeC4 grammar: tags before properties)
    if node_instances:
        system_tags: set[str] = set()
        for app_path in node_instances:
            parts = app_path.split('.')
            if len(parts) >= 2:
                system_tags.add(f'system_{parts[1]}')
        if system_tags:
            lines.append(f"{pad}  #{' #'.join(sorted(system_tags))}")
    if node.documentation:
        desc = truncate_desc(escape_str(node.documentation))
        lines.append(f"{pad}  description '{desc}'")
    render_metadata(lines, node.archi_id, pad, extra={'tech_type': node.tech_type})
    # Collect used names from children to avoid instanceOf name collisions
    used_names: set[str] = {child.c4_id for child in node.children}
    for app_path in node_instances:
        base_name = app_path.rsplit('.', 1)[-1]
        if base_name in used_names:
            suffix = 2
            alias = f'{base_name}_{suffix}'
            while alias in used_names:
                suffix += 1
                alias = f'{base_name}_{suffix}'
            used_names.add(alias)
            lines.append(f'{pad}  {alias} = instanceOf {app_path}')
        else:
            used_names.add(base_name)
            lines.append(f'{pad}  instanceOf {app_path}')
    for child in sorted(node.children, key=lambda c: c.name):
        lines.append('')
        child_path = f'{current_path}.{child.c4_id}'
        _render_deployment_node(child, lines, indent + 2, child_path, instances)
    lines.append(f'{pad}}}')


def generate_deployment_c4(
    nodes: list[DeploymentNode],
    deployment_map: list[tuple[str, str]] | None = None,
    env: str = 'prod',
) -> str:
    """Generate deployment/topology.c4 using the LikeC4 Deployment Model.

    Wraps the topology in ``deployment { environment <env> { ... } }`` and
    adds ``instanceOf <app_c4_path>`` inside each infrastructure node that has
    application components deployed to it (as per deployment_map).
    """
    # Build inverse index: full infra path → [app c4 paths]
    instances: dict[str, list[str]] = {}
    if deployment_map:
        for app_path, infra_path in deployment_map:
            instances.setdefault(infra_path, []).append(app_path)

    lines = [
        '// ── Deployment Topology ──────────────────────────────────',
        'deployment {',
        '',
        f'  environment {env} {{',
        '',
    ]
    for node in sorted(nodes, key=lambda n: n.name):
        _render_deployment_node(node, lines, indent=4, current_path=node.c4_id, instances=instances)
        lines.append('')
    lines.append('  }')
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


def generate_deployment_overview_view(env: str = 'prod') -> str:
    """Generate views/deployment-architecture.c4 using deployment view syntax."""
    return f"""\
views {{

  deployment view deployment_architecture {{
    title 'Deployment Architecture'
    include {env}.**
  }}

}}
"""
