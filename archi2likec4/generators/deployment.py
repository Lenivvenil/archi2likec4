"""Generate deployment topology .c4 files."""

from __future__ import annotations

import logging

from ..models import DEFAULT_DEPLOYMENT_KIND, INSTANCE_ALLOWED_KINDS, DeploymentNode, System
from ..utils import escape_str, extract_system_id
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


def _compute_ancestor_tags(
    instances: dict[str, list[str]],
    sys_subdomain: dict[str, str] | None = None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
) -> dict[str, set[str]]:
    """Propagate system tags from host nodes up to all ancestor paths.

    For each host path in *instances*, extracts ``system_<id>`` tags from the
    app paths and assigns them to every ancestor prefix.  This lets structural
    nodes (racks, hypervisors, DCs) carry the same tags so deployment views can
    ``exclude`` empty branches.
    """
    ancestor_tags: dict[str, set[str]] = {}
    for infra_path, app_paths in instances.items():
        sys_tags: set[str] = set()
        for ap in app_paths:
            sid = extract_system_id(ap, sys_subdomain, sys_ids, sys_domain)
            sys_tags.add(f'system_{sid}')
        if not sys_tags:
            continue
        # Walk up the path: dc1.rack1.esxi → dc1.rack1 → dc1
        path_parts = infra_path.split('.')
        for i in range(len(path_parts) - 1):  # exclude the host itself (tagged separately)
            prefix = '.'.join(path_parts[: i + 1])
            ancestor_tags.setdefault(prefix, set()).update(sys_tags)
    return ancestor_tags


def _render_deployment_node(
    node: DeploymentNode,
    lines: list[str],
    indent: int,
    current_path: str,
    instances: dict[str, list[str]],
    ancestor_tags: dict[str, set[str]],
    sys_subdomain: dict[str, str] | None = None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
    parent_kind: str | None = None,
) -> None:
    """Recursively render a DeploymentNode and its children.

    Appends ``instanceOf <app_path>`` for each application mapped to this node
    via the deployment_map passed to :func:`generate_deployment_c4`.

    Orphan infraSoftware (top-level, no parent except environment) is dropped.
    """
    # Drop orphan infraSoftware at top level
    if node.kind == 'infraSoftware' and parent_kind in (None, 'environment'):
        logger.warning("Dropping orphan infraSoftware '%s' (%s)", node.name, node.archi_id)
        return

    pad = ' ' * indent
    title = escape_str(node.name)
    node_instances = instances.get(current_path, [])
    lines.append(f"{pad}{node.c4_id} = {node.kind} '{title}' {{")
    # System tags FIRST (LikeC4 grammar: tags before properties)
    if node_instances:
        system_tags: set[str] = set()
        for app_path in node_instances:
            sid = extract_system_id(app_path, sys_subdomain, sys_ids, sys_domain)
            system_tags.add(f'system_{sid}')
        if system_tags:
            lines.append(f"{pad}  #{' #'.join(sorted(system_tags))}")
    elif current_path in ancestor_tags:
        lines.append(f"{pad}  #{' #'.join(sorted(ancestor_tags[current_path]))}")
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
        _render_deployment_node(child, lines, indent + 2, child_path, instances, ancestor_tags,
                                sys_subdomain, sys_ids, sys_domain, parent_kind=node.kind)
    lines.append(f'{pad}}}')


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


def generate_deployment_c4(
    nodes: list[DeploymentNode],
    deployment_map: list[tuple[str, str]] | None = None,
    env: str = 'prod',
    *,
    sys_subdomain: dict[str, str] | None = None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
) -> str:
    """Generate deployment/topology.c4 using the LikeC4 Deployment Model.

    Wraps the topology in ``deployment { environment <env> { ... } }`` and
    adds ``instanceOf <app_c4_path>`` inside each infrastructure node that has
    application components deployed to it (as per deployment_map).

    instanceOf is only placed on leaf compute nodes (vm, server, namespace).
    Placements on structural nodes (site, segment, cluster) are filtered out.
    """
    # Build node kind map for instanceOf filtering
    node_kinds = _build_node_kind_map(nodes)

    # Build inverse index: full infra path → [app c4 paths]
    # Filter: only allow instanceOf on leaf compute kinds
    instances: dict[str, list[str]] = {}
    skipped = 0
    if deployment_map:
        for app_path, infra_path in deployment_map:
            node_kind = node_kinds.get(infra_path, DEFAULT_DEPLOYMENT_KIND)
            if node_kind not in INSTANCE_ALLOWED_KINDS:
                skipped += 1
                continue
            instances.setdefault(infra_path, []).append(app_path)

    if skipped:
        logger.info(
            "Filtered %d instanceOf placements on structural nodes "
            "(only %s can host instances)",
            skipped, ', '.join(sorted(INSTANCE_ALLOWED_KINDS)),
        )

    ancestor_tags = _compute_ancestor_tags(instances, sys_subdomain, sys_ids, sys_domain)

    # Collect ALL system tags for the environment node (must survive all exclude rules)
    all_sys_tags: set[str] = set()
    for tags in ancestor_tags.values():
        all_sys_tags.update(tags)
    for app_paths in instances.values():
        for ap in app_paths:
            sid = extract_system_id(ap, sys_subdomain, sys_ids, sys_domain)
            all_sys_tags.add(f'system_{sid}')

    lines = [
        '// ── Deployment Topology ──────────────────────────────────',
        'deployment {',
        '',
        f'  environment {env} {{',
    ]
    if all_sys_tags:
        lines.append(f"    #{' #'.join(sorted(all_sys_tags))}")
    lines.append('')
    for node in sorted(nodes, key=lambda n: n.name):
        _render_deployment_node(node, lines, indent=4, current_path=node.c4_id, instances=instances,
                                ancestor_tags=ancestor_tags, sys_subdomain=sys_subdomain,
                                sys_ids=sys_ids, sys_domain=sys_domain, parent_kind='environment')
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


def _collect_all_paths(
    nodes: list[DeploymentNode],
    prefix: str = '',
    parent_kind: str | None = None,
) -> list[str]:
    """Collect all node paths from the deployment tree (for star-chain includes).

    LikeC4 deployment views do not support ``.**`` (deep wildcard).  Instead,
    ``include path.*`` must be emitted for every intermediate level.

    Orphan infraSoftware (top-level, no real parent) is excluded — matching the
    same filter as :func:`_render_deployment_node`.
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


def generate_system_deployment_views(
    nodes: list[DeploymentNode] | None = None,
    deployment_map: list[tuple[str, str]] | None = None,
    systems: list[System] | None = None,
    env: str = 'prod',
    *,
    sys_subdomain: dict[str, str] | None = None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
) -> str:
    """Generate per-system deployment views using star-chain + tag exclude.

    LikeC4 deployment views do not support ``include env.**``.  For each
    system we emit star-chain includes for all tree levels, then
    ``exclude * where tag is not #system_<id>`` to filter.

    Returns a single ``.c4`` string with all per-system views, or empty string
    if there are no deployments.
    """
    if not deployment_map or not systems or not nodes:
        return ''

    # Build reverse index: system_tag → set of infra paths
    system_infra: dict[str, set[str]] = {}
    for app_path, infra_path in deployment_map:
        sid = extract_system_id(app_path, sys_subdomain, sys_ids, sys_domain)
        system_infra.setdefault(sid, set()).add(infra_path)

    if not system_infra:
        return ''

    # Build system name lookup: sanitized c4_id → display name
    sys_names: dict[str, str] = {}
    for s in systems:
        tag_id = s.c4_id.replace('-', '_')
        sys_names[tag_id] = s.name

    # Precompute all tree paths for star-chain
    all_paths = sorted(set(_collect_all_paths(nodes)))

    lines = ['views {']
    generated = 0
    for sid in sorted(system_infra):
        name = escape_str(sys_names.get(sid, sid))

        lines.append('')
        lines.append(f'  deployment view {sid}_deploy {{')
        lines.append(f"    title '{name} — {env}'")
        lines.append('')
        lines.append(f'    include {env}')
        lines.append(f'    include {env}.*')
        for p in all_paths:
            lines.append(f'    include {env}.{p}.*')
        lines.append('')
        lines.append(f'    exclude * where tag is not #system_{sid}')
        lines.append('  }')
        generated += 1

    lines.append('')
    lines.append('}')
    lines.append('')

    if not generated:
        return ''

    logger.info('Generated %d per-system deployment views', generated)
    return '\n'.join(lines)
