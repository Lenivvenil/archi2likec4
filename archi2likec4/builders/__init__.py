"""Builders package: transform parsed elements into the output model.

All public symbols are re-exported here for backward compatibility.
"""

from ..utils import flatten_deployment_nodes
from .data import build_data_access, build_data_entities, build_datastore_entity_links
from .deployment import (
    build_archi_to_c4_map,
    build_deployment_map,
    build_deployment_topology,
    build_tech_archi_to_c4_map,
    enrich_deployment_from_visual_nesting,
)
from .domains import apply_domain_prefix, assign_domains, assign_subdomains
from .integrations import build_integrations
from .systems import attach_functions, attach_interfaces, build_systems

# Backward-compat alias (Task 1 moved the real impl to utils)
_flatten_deployment_nodes = flatten_deployment_nodes

__all__ = [
    'apply_domain_prefix',
    'assign_domains',
    'assign_subdomains',
    'attach_functions',
    'attach_interfaces',
    'build_archi_to_c4_map',
    'build_data_access',
    'build_data_entities',
    'build_datastore_entity_links',
    'build_deployment_map',
    'build_deployment_topology',
    'build_integrations',
    'build_systems',
    'build_tech_archi_to_c4_map',
    'enrich_deployment_from_visual_nesting',
    '_flatten_deployment_nodes',
]
