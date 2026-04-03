"""Generate deployment topology .c4 files."""

from __future__ import annotations

import logging

from ..models import DeploymentNode
from ..utils import escape_str
from ._common import render_metadata, truncate_desc

logger = logging.getLogger(__name__)


def _build_node_kind_map(
    nodes: list[DeploymentNode],
    prefix: str = '',
) -> dict[str, str]:
    """Build mapping of node paths to their resolved kinds."""
    result: dict[str, str] = {}
    for node in nodes:
        path = f'{prefix}.{node.c4_id}' if prefix else node.c4_id
        result[path] = node.kind
        result.update(_build_node_kind_map(node.children, prefix=path))
    return result


def _render_infra_node(
    node: DeploymentNode,
    lines: list[str],
    indent: int,
    parent_kind: str | None = None,
) -> None:
    """Render a DeploymentNode for infrastructure files (no instanceOf, no tags)."""
    if node.kind == 'infraSoftware' and parent_kind in (None, 'environment'):
        logger.warning("Dropping orphan infraSoftware '%s' (%s)", node.name, node.archi_id)
        return

    pad = ' ' * indent
    title = escape_str(node.name)
    lines.append(f"{pad}{node.c4_id} = {node.kind} '{title}' {{")
    if node.documentation:
        desc = truncate_desc(escape_str(node.documentation))
        lines.append(f"{pad}  description '{desc}'")
    render_metadata(lines, node.archi_id, pad, extra={'tech_type': node.tech_type})
    for child in sorted(node.children, key=lambda c: c.name):
        lines.append('')
        _render_infra_node(child, lines, indent + 2, parent_kind=node.kind)
    lines.append(f'{pad}}}')


def generate_infrastructure_files(
    nodes: list[DeploymentNode],
    env: str = 'prod',
) -> dict[str, str]:
    """Generate infrastructure/ files: environments.c4 + one file per top-level site.

    Returns a dict of filename → content (relative to infrastructure/ dir).
    Each site file uses ``deployment { extend <env> { ... } }`` so LikeC4
    merges them across files.
    """
    # environments.c4 — environment declaration
    env_lines = [
        '// ── Deployment Environments ──────────────────────────────────',
        'deployment {',
        '',
        f"  environment {env} {{",
        '  }',
        '',
        '}',
        '',
    ]
    files: dict[str, str] = {'environments.c4': '\n'.join(env_lines)}

    # One file per top-level site node
    for node in sorted(nodes, key=lambda n: n.name):
        if node.kind == 'infraSoftware' and True:  # top-level orphan check
            continue
        site_lines = [
            f'// ── {node.name} ──────────────────────────────────',
            'deployment {',
            '',
            f'  extend {env} {{',
            '',
        ]
        _render_infra_node(node, site_lines, indent=4, parent_kind='environment')
        site_lines.append('')
        site_lines.append('  }')
        site_lines.append('}')
        site_lines.append('')
        files[f'{node.c4_id}.c4'] = '\n'.join(site_lines)

    return files


def generate_system_deployment_c4(
    system_c4_id: str,
    system_name: str,
    deploy_entries: list[tuple[str, str]],
    env: str = 'prod',
) -> str:
    """Generate systems/{name}/deployment.c4 with extend blocks + deployment view.

    Each *deploy_entries* item is ``(app_c4_path, infra_c4_path)`` where
    infra_c4_path is a host node (vm, server, namespace) for this system.

    Generates:
    - ``extend {env}.{infra_path} { instanceOf {app_path} }`` blocks
    - A deployment view with targeted ``include {env}.{infra_path}.**`` lines
    """
    if not deploy_entries:
        return ''

    # Group by infra path: each VM → list of app paths deployed there
    infra_apps: dict[str, list[str]] = {}
    for app_path, infra_path in deploy_entries:
        infra_apps.setdefault(infra_path, []).append(app_path)

    lines = [
        f'// ── {escape_str(system_name)} (deployment) ──────────────────────────',
        'deployment {',
        '',
    ]

    for infra_path in sorted(infra_apps):
        lines.append(f'  extend {env}.{infra_path} {{')
        used_names: set[str] = set()
        for app_path in infra_apps[infra_path]:
            base_name = app_path.rsplit('.', 1)[-1]
            if base_name in used_names:
                suffix = 2
                alias = f'{base_name}_{suffix}'
                while alias in used_names:
                    suffix += 1
                    alias = f'{base_name}_{suffix}'
                used_names.add(alias)
                lines.append(f'    {alias} = instanceOf {app_path}')
            else:
                used_names.add(base_name)
                lines.append(f'    instanceOf {app_path}')
        lines.append('  }')
        lines.append('')

    lines.append('}')
    lines.append('')

    # Deployment view with targeted includes (no tags, no excludes)
    view_id = system_c4_id.replace('-', '_')
    lines.append('views {')
    lines.append('')
    lines.append(f'  deployment view {view_id}_deployment {{')
    lines.append(f"    title '{escape_str(system_name)} — {env}'")
    lines.append('')
    for infra_path in sorted(infra_apps):
        lines.append(f'    include {env}.{infra_path}.*')
    lines.append('  }')
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


def _collect_all_paths(
    nodes: list[DeploymentNode],
    prefix: str = '',
    parent_kind: str | None = None,
) -> list[str]:
    """Collect all node paths from the deployment tree (for star-chain includes).

    LikeC4 deployment views do not support ``.**`` (deep wildcard).  Instead,
    ``include path.*`` must be emitted for every intermediate level.

    Orphan infraSoftware (top-level, no real parent) is excluded.
    """
    paths: list[str] = []
    for node in nodes:
        if node.kind == 'infraSoftware' and parent_kind in (None, 'environment'):
            continue
        path = f'{prefix}.{node.c4_id}' if prefix else node.c4_id
        paths.append(path)
        paths.extend(_collect_all_paths(node.children, path, parent_kind=node.kind))
    return paths


def generate_deployment_overview_view(
    nodes: list[DeploymentNode] | None = None,
    env: str = 'prod',
) -> str:
    """Generate views/deployment-architecture.c4 using star-chain includes.

    LikeC4 deployment views do not support ``include env.**``.  We emit
    ``include env`` + ``include env.*`` + ``include env.X.*`` for every
    intermediate path in the deployment tree.
    """
    lines = [
        'views {',
        '',
        '  deployment view deployment_architecture {',
        "    title 'Deployment Architecture'",
    ]
    if nodes:
        all_paths = _collect_all_paths(nodes)
        lines.append(f'    include {env}')
        lines.append(f'    include {env}.*')
        for p in sorted(set(all_paths)):
            lines.append(f'    include {env}.{p}.*')
    else:
        lines.append(f'    include {env}')
    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


