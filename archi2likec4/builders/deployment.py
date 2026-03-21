"""Builders: deployment topology and archi→c4 mapping."""

import logging

from ..models import (
    DeploymentNode,
    RawRelationship,
    System,
    TechElement,
)
from ..utils import flatten_deployment_nodes, make_id, make_unique_id

logger = logging.getLogger(__name__)


_INFRA_NODE_TYPES = frozenset({
    'Node', 'Device', 'TechnologyCollaboration',
})
_INFRA_ZONE_TYPES = frozenset({
    'CommunicationNetwork', 'Path',
})
_INFRA_SW_TYPES = frozenset({
    'SystemSoftware', 'TechnologyService', 'Artifact',
})


def build_deployment_topology(
    tech_elements: list[TechElement],
    relationships: list[RawRelationship],
) -> list[DeploymentNode]:
    """Build deployment hierarchy from tech elements and AggregationRelationship.

    AggregationRelationship source contains target:
    - TechnologyCollaboration → Node (cluster contains servers)
    - Node → SystemSoftware (server contains software)
    - Device → SystemSoftware (device contains software)

    Returns only root nodes (elements not contained by anything).
    """
    if not tech_elements:
        return []

    # 1. Create DeploymentNode for each TechElement with unique c4_ids
    used_ids: set[str] = set()
    node_by_archi: dict[str, DeploymentNode] = {}

    for te in tech_elements:
        c4_id = make_unique_id(make_id(te.name), used_ids)
        used_ids.add(c4_id)

        if te.tech_type == 'Location':
            kind = 'infraLocation'
        elif te.tech_type in _INFRA_ZONE_TYPES:
            kind = 'infraZone'
        elif te.tech_type in _INFRA_NODE_TYPES:
            kind = 'infraNode'
        else:
            # All remaining types (_INFRA_SW_TYPES: SystemSoftware, TechnologyService, Artifact,
            # and unknown types: TechnologyFunction, TechnologyProcess, etc.) become infraSoftware.
            # infraNode is reserved for explicit Node/Device/TechnologyCollaboration (containers).
            kind = 'infraSoftware'
            if te.tech_type not in _INFRA_SW_TYPES:
                logger.debug('Unknown tech_type %r for %r — defaulting to infraSoftware',
                             te.tech_type, te.name)

        dn = DeploymentNode(
            c4_id=c4_id,
            name=te.name,
            archi_id=te.archi_id,
            tech_type=te.tech_type,
            kind=kind,
            documentation=te.documentation,
        )
        node_by_archi[te.archi_id] = dn

    # 2. Resolve AggregationRelationship → parent contains children
    children_set: set[str] = set()  # archi_ids that are children

    for rel in relationships:
        if rel.rel_type != 'AggregationRelationship':
            continue
        parent = node_by_archi.get(rel.source_id)
        child = node_by_archi.get(rel.target_id)
        if parent and child and rel.target_id not in children_set:
            parent.children.append(child)
            children_set.add(rel.target_id)

    # 3. Return only root nodes (not children of anything)
    roots = [dn for aid, dn in node_by_archi.items() if aid not in children_set]
    roots.sort(key=lambda n: n.name)

    logger.debug('%d tech elements → %d root deployment nodes',
                 len(tech_elements), len(roots))
    return roots


def enrich_deployment_from_visual_nesting(
    deployment_nodes: list[DeploymentNode],
    visual_nesting_pairs: list[tuple[str, str]],
) -> int:
    """Use visual nesting from Archi diagrams to fix missing parent-child relationships.

    When a tech element appears as a root node but a deployment diagram shows it
    visually nested inside another tech element, re-parent it. This fixes the common
    case where Archi has no AggregationRelationship but the diagram canvas shows nesting.

    Mutates deployment_nodes in-place. Returns the count of re-parented nodes.
    """
    if not visual_nesting_pairs:
        return 0

    # Build flat index: archi_id → DeploymentNode
    all_nodes = flatten_deployment_nodes(deployment_nodes)
    by_archi: dict[str, DeploymentNode] = {dn.archi_id: dn for dn in all_nodes}
    root_ids = {dn.archi_id for dn in deployment_nodes}

    # Deduplicate and filter: only consider pairs where both sides are known tech elements
    # and the child is currently a root node
    reparent: dict[str, str] = {}  # child_archi_id → parent_archi_id
    for parent_aid, child_aid in visual_nesting_pairs:
        if parent_aid not in by_archi or child_aid not in by_archi:
            continue
        if child_aid not in root_ids:
            continue  # already nested
        if child_aid == parent_aid:
            continue
        # First diagram wins (most authoritative)
        if child_aid not in reparent:
            reparent[child_aid] = parent_aid

    # Apply reparenting
    moved_aids: set[str] = set()
    for child_aid, parent_aid in reparent.items():
        child = by_archi[child_aid]
        parent = by_archi[parent_aid]
        # Avoid cycles: don't reparent if parent is descendant of child
        if _is_descendant(child, parent_aid):
            continue
        # Check child is not already a child of parent
        if any(c.archi_id == child_aid for c in parent.children):
            continue
        parent.children.append(child)
        moved_aids.add(child_aid)

    # Remove reparented nodes from root list
    reparented = len(moved_aids)
    if reparented:
        deployment_nodes[:] = [dn for dn in deployment_nodes if dn.archi_id not in moved_aids]
        deployment_nodes.sort(key=lambda n: n.name)

    if reparented:
        logger.info('Re-parented %d deployment nodes from visual nesting', reparented)

    return reparented


def _is_descendant(node: DeploymentNode, target_archi_id: str) -> bool:
    """Check if target_archi_id is a descendant of node."""
    for child in node.children:
        if child.archi_id == target_archi_id:
            return True
        if _is_descendant(child, target_archi_id):
            return True
    return False


def _build_deployment_path_index(
    nodes: list[DeploymentNode],
    prefix: str = '',
) -> dict[str, str]:
    """Build archi_id → qualified c4 path for all nodes in the tree.

    Root nodes get their c4_id as path; nested nodes get parent.child paths.
    """
    result: dict[str, str] = {}
    for node in nodes:
        path = f'{prefix}{node.c4_id}' if not prefix else f'{prefix}.{node.c4_id}'
        result[node.archi_id] = path
        result.update(_build_deployment_path_index(node.children, path))
    return result


def build_tech_archi_to_c4_map(
    deployment_nodes: list[DeploymentNode],
) -> dict[str, str]:
    """Build archi_id → c4_path for all deployment nodes (public wrapper)."""
    return _build_deployment_path_index(deployment_nodes)


def _build_app_path_index(
    systems: list[System],
    sys_domain: dict[str, str],
    sys_subdomain: dict[str, str] | None,
) -> dict[str, str]:
    """Build archi_id → full c4 path index for systems and subsystems."""
    app_path: dict[str, str] = {}
    for sys in systems:
        domain = sys_domain.get(sys.c4_id, 'unassigned')
        subdomain = sys_subdomain.get(sys.c4_id, '') if sys_subdomain else ''
        full = f'{domain}.{subdomain}.{sys.c4_id}' if subdomain else f'{domain}.{sys.c4_id}'
        if sys.archi_id:
            app_path[sys.archi_id] = full
        for eid in sys.extra_archi_ids:
            app_path[eid] = full
        for sub in sys.subsystems:
            if sub.archi_id:
                app_path[sub.archi_id] = f'{full}.{sub.c4_id}'
    return app_path


def build_deployment_map(
    systems: list[System],
    deployment_nodes: list[DeploymentNode],
    relationships: list[RawRelationship],
    sys_domain: dict[str, str],
    sys_subdomain: dict[str, str] | None = None,
    promoted_archi_to_c4: dict[str, list[str]] | None = None,
) -> list[tuple[str, str]]:
    """Build (app_c4_path, node_c4_path) pairs from cross-layer RealizationRelationship.

    Resolves ApplicationComponent ↔ Node/SystemSoftware/Device via RealizationRelationship.
    When a promoted parent archi_id is encountered, fans out to all child system paths.
    """
    if not deployment_nodes or not systems:
        return []

    app_path = _build_app_path_index(systems, sys_domain, sys_subdomain)

    # Build tech index: archi_id → qualified c4 path (parent.child for nested)
    tech_path = _build_deployment_path_index(deployment_nodes)

    # Only ApplicationComponent is resolvable via app_path (systems/subsystems).
    _app_types = {'ApplicationComponent'}
    _tech_types = {'Node', 'SystemSoftware', 'Device', 'TechnologyCollaboration',
                   'TechnologyService', 'Artifact', 'CommunicationNetwork', 'Path',
                   'TechnologyFunction', 'TechnologyProcess', 'TechnologyInteraction'}

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for rel in relationships:
        if rel.rel_type not in ('RealizationRelationship', 'AssignmentRelationship'):
            continue

        app_id: str | None = None
        tech_id: str | None = None

        if rel.source_type in _app_types and rel.target_type in _tech_types:
            app_id, tech_id = rel.source_id, rel.target_id
        elif rel.source_type in _tech_types and rel.target_type in _app_types:
            app_id, tech_id = rel.target_id, rel.source_id
        else:
            continue

        app_paths_resolved: list[str] = []
        a = app_path.get(app_id)
        if a:
            app_paths_resolved.append(a)
        elif promoted_archi_to_c4 and app_id in promoted_archi_to_c4:
            app_paths_resolved.extend(promoted_archi_to_c4[app_id])

        t = tech_path.get(tech_id)
        if not app_paths_resolved or not t:
            continue

        for a in app_paths_resolved:
            pair = (a, t)
            if pair in seen:
                continue
            seen.add(pair)
            result.append(pair)

    result.sort()
    return result


_LEAF_KINDS = frozenset({'infraSoftware'})


def validate_deployment_tree(
    deployment_nodes: list[DeploymentNode],
) -> list[str]:
    """Validate structural invariants on the final deployment tree.

    Returns a list of violation descriptions (empty if all ok).
    Checks:
    (a) leaf nodes (infraSoftware) have no children
    (b) no duplicate archi_id across the tree
    (c) sibling c4_id uniqueness within each parent
    (d) qualified paths contain no '..' (double dot)
    """
    violations: list[str] = []

    from ..utils import flatten_deployment_nodes

    all_nodes = flatten_deployment_nodes(deployment_nodes)

    # (a) Leaf nodes must not have children
    for node in all_nodes:
        if node.kind in _LEAF_KINDS and node.children:
            child_names = ', '.join(c.name for c in node.children)
            violations.append(
                f'Leaf {node.kind} "{node.name}" ({node.archi_id}) has children: {child_names}')

    # (b) No duplicate archi_id
    seen_archi: dict[str, str] = {}
    for node in all_nodes:
        if node.archi_id in seen_archi:
            violations.append(
                f'Duplicate archi_id {node.archi_id}: '
                f'"{node.name}" and "{seen_archi[node.archi_id]}"')
        else:
            seen_archi[node.archi_id] = node.name

    # (c) Sibling c4_id uniqueness
    def _check_sibling_uniqueness(children: list[DeploymentNode], parent_name: str) -> None:
        seen_c4: dict[str, str] = {}
        for child in children:
            if child.c4_id in seen_c4:
                violations.append(
                    f'Duplicate sibling c4_id "{child.c4_id}" under "{parent_name}": '
                    f'"{child.name}" and "{seen_c4[child.c4_id]}"')
            else:
                seen_c4[child.c4_id] = child.name
            _check_sibling_uniqueness(child.children, child.name)

    _check_sibling_uniqueness(deployment_nodes, '<root>')

    # (d) Qualified paths must not contain '..'
    paths = _build_deployment_path_index(deployment_nodes)
    for archi_id, path in paths.items():
        if '..' in path:
            node_name = seen_archi.get(archi_id, '?')
            violations.append(
                f'Double-dot in qualified path for "{node_name}": {path}')

    return violations


def build_archi_to_c4_map(
    systems: list[System],
    sys_domain: dict[str, str],
    iface_c4_path: dict[str, str] | None = None,
    sys_subdomain: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a complete archi_id → c4_path mapping for all elements.

    Includes systems, subsystems, appFunctions, and optionally interfaces.
    Returns dict: archi_id → full c4 path (e.g. 'products.banking.efs.account_service.fn_create')
    """
    result: dict[str, str] = {}
    for sys in systems:
        domain = sys_domain.get(sys.c4_id, 'unassigned')
        subdomain = sys_subdomain.get(sys.c4_id, '') if sys_subdomain else ''
        sys_path = f'{domain}.{subdomain}.{sys.c4_id}' if subdomain else f'{domain}.{sys.c4_id}'
        if sys.archi_id:
            result[sys.archi_id] = sys_path
        for eid in sys.extra_archi_ids:
            result[eid] = sys_path
        for sub in sys.subsystems:
            sub_path = f'{sys_path}.{sub.c4_id}'
            if sub.archi_id:
                result[sub.archi_id] = sub_path
            for fn in sub.functions:
                if fn.archi_id:
                    result[fn.archi_id] = f'{sub_path}.{fn.c4_id}'
        for fn in sys.functions:
            if fn.archi_id:
                result[fn.archi_id] = f'{sys_path}.{fn.c4_id}'
    # Add interfaces — resolve to their owner system path
    if iface_c4_path:
        for iface_id, iface_path in iface_c4_path.items():
            if iface_id not in result:
                # Resolve system c4_id to domain(.subdomain).system path
                sys_c4_id = iface_path.split('.')[0]
                domain = sys_domain.get(sys_c4_id, 'unassigned')
                sd = sys_subdomain.get(sys_c4_id, '') if sys_subdomain else ''
                if sd:
                    result[iface_id] = f'{domain}.{sd}.{iface_path}'
                else:
                    result[iface_id] = f'{domain}.{iface_path}'
    return result
