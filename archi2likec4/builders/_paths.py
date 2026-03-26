"""Shared path-index helpers for builder submodules."""

from __future__ import annotations

from ..models import DeploymentNode, System


def build_comp_c4_path(systems: list[System]) -> dict[str, str]:
    """Build archi_id → c4_path map (system or subsystem full path)."""
    comp_c4_path: dict[str, str] = {}
    for sys in systems:
        if sys.archi_id:
            comp_c4_path[sys.archi_id] = sys.c4_id
        for eid in sys.extra_archi_ids:
            comp_c4_path[eid] = sys.c4_id
        for sub in sys.subsystems:
            if sub.archi_id:
                comp_c4_path[sub.archi_id] = f'{sys.c4_id}.{sub.c4_id}'
    return comp_c4_path


def build_deployment_path_index(
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
        result.update(build_deployment_path_index(node.children, path))
    return result
