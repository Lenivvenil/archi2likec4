"""Generators package: produce LikeC4 .c4 file content from the output model."""

from .domains import generate_domain_c4
from .spec import generate_spec
from .systems import generate_system_detail_c4
from .views import (
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_landscape_view,
)

__all__ = [
    'generate_domain_c4',
    'generate_domain_functional_view',
    'generate_domain_integration_view',
    'generate_landscape_view',
    'generate_spec',
    'generate_system_detail_c4',
]
