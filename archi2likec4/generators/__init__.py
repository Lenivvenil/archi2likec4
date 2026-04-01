"""Generators package: produce LikeC4 .c4 file content from the output model."""

from .audit import generate_audit_md
from .deployment import (
    generate_datastore_mapping_c4,
    generate_deployment_c4,
    generate_deployment_overview_view,
)
from .domains import generate_domain_c4
from .entities import generate_entities
from .relationships import generate_relationships
from .spec import generate_spec
from .systems import generate_system_detail_c4
from .views import (
    ViewContext,
    build_view_context,
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_landscape_view,
    generate_persistence_map,
    generate_solution_views,
)

__all__ = [
    'ViewContext',
    'build_view_context',
    'generate_audit_md',
    'generate_datastore_mapping_c4',
    'generate_deployment_c4',
    'generate_deployment_overview_view',
    'generate_domain_c4',
    'generate_domain_functional_view',
    'generate_domain_integration_view',
    'generate_entities',
    'generate_landscape_view',
    'generate_persistence_map',
    'generate_relationships',
    'generate_solution_views',
    'generate_spec',
    'generate_system_detail_c4',
]
