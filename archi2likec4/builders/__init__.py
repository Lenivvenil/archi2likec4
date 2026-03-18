"""Builders package: transform parsed elements into the output model.

All public symbols are re-exported here for backward compatibility.
"""

from ._result import BuildResult
from .data import build_data_access, build_data_entities, build_datastore_entity_links
from .deployment import (
    build_archi_to_c4_map,
    build_deployment_map,
    build_deployment_topology,
    build_tech_archi_to_c4_map,
    enrich_deployment_from_visual_nesting,
    validate_deployment_tree,
)
from .domains import apply_domain_prefix, assign_domains, assign_subdomains
from .integrations import build_integrations
from .systems import attach_functions, attach_interfaces, build_systems

__all__ = [
    'BuildResult',
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
    'validate_deployment_tree',
]
