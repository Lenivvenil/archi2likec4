"""Shared mock objects for tests."""

from pathlib import Path

from archi2likec4.builders._result import BuildDiagnostics
from archi2likec4.models import DEFAULT_PROP_MAP, DEFAULT_STANDARD_KEYS


class MockConfig:
    """Mock for ConvertConfig — all fields with defaults matching ConvertConfig."""
    def __init__(
        self,
        promote_children=None,
        promote_warn_threshold=10,
        audit_suppress=None,
        audit_suppress_incidents=None,
        domain_overrides=None,
        reviewed_systems=None,
        language='ru',
        subdomain_overrides=None,
        strict=False,
        verbose=False,
        dry_run=False,
        max_unresolved_ratio=0.5,
        max_orphan_functions_warn=5,
        max_unassigned_systems_warn=20,
        domain_renames=None,
        extra_domain_patterns=None,
        model_root=None,
        output_dir=None,
        property_map=None,
        standard_keys=None,
        deployment_env='prod',
        sync_target=None,
        extra_view_patterns=None,
        sync_protected_top=None,
        sync_protected_paths=None,
        spec_colors=None,
        spec_shapes=None,
        spec_tags=None,
    ):
        self.promote_children = promote_children or {}
        self.promote_warn_threshold = promote_warn_threshold
        self.audit_suppress = audit_suppress or []
        self.audit_suppress_incidents = audit_suppress_incidents or []
        self.domain_overrides = domain_overrides or {}
        self.reviewed_systems = reviewed_systems or []
        self.language = language
        self.subdomain_overrides = subdomain_overrides or {}
        self.strict = strict
        self.verbose = verbose
        self.dry_run = dry_run
        self.max_unresolved_ratio = max_unresolved_ratio
        self.max_orphan_functions_warn = max_orphan_functions_warn
        self.max_unassigned_systems_warn = max_unassigned_systems_warn
        self.domain_renames = domain_renames or {}
        self.extra_domain_patterns = extra_domain_patterns or []
        self.model_root = model_root if model_root is not None else Path('architectural_repository/model')
        self.output_dir = output_dir if output_dir is not None else Path('output')
        self.property_map = property_map if property_map is not None else dict(DEFAULT_PROP_MAP)
        self.standard_keys = standard_keys if standard_keys is not None else list(DEFAULT_STANDARD_KEYS)
        self.deployment_env = deployment_env
        self.extra_view_patterns = extra_view_patterns if extra_view_patterns is not None else [
            {'pattern': r'^Функциональная архитектура[.\s]+(.+)$', 'view_type': 'functional'},
            {'pattern': r'^Интеграционная архитектура[.\s]+(.+)$', 'view_type': 'integration'},
            {'pattern': r'^Схема разв[её]ртывания[.\s]+(.+)$', 'view_type': 'deployment'},
        ]
        self.sync_target = sync_target
        self.sync_protected_top = sync_protected_top if sync_protected_top is not None else frozenset()
        self.sync_protected_paths = sync_protected_paths if sync_protected_paths is not None else frozenset()
        self.spec_colors = spec_colors if spec_colors is not None else {
            'archi-app': '#7EB8DA', 'archi-app-light': '#BDE0F0',
            'archi-data': '#F0D68A', 'archi-store': '#B0B0B0',
            'archi-tech': '#93D275', 'archi-tech-light': '#C5E6B8',
        }
        self.spec_shapes = spec_shapes if spec_shapes is not None else {
            'domain': 'rectangle', 'subdomain': 'rectangle',
            'system': 'component', 'subsystem': 'component',
            'appFunction': 'rectangle', 'dataEntity': 'document',
            'dataStore': 'cylinder', 'infraNode': 'rectangle',
            'infraSoftware': 'cylinder', 'infraZone': 'rectangle',
            'infraLocation': 'rectangle',
        }
        self.spec_tags = spec_tags if spec_tags is not None else [
            'to_review', 'external', 'entity', 'store',
            'infrastructure', 'cluster', 'device', 'network',
        ]


class MockBuilt:
    """Mock for BuildResult — all fields with defaults."""
    def __init__(
        self,
        systems=None,
        domain_systems=None,
        integrations=None,
        entities=None,
        deployment_map=None,
        diagnostics=None,
        relationships=None,
        deployment_nodes=None,
        datastore_entity_links=None,
        subdomains=None,
        subdomain_systems=None,
        # Additional BuildResult fields
        data_access=None,
        sys_domain=None,
        archi_to_c4=None,
        promoted_archi_to_c4=None,
        promoted_parents=None,
        iface_c4_path=None,
        tech_archi_to_c4=None,
    ):
        self.systems = systems or []
        self.domain_systems = domain_systems or {}
        self.integrations = integrations or []
        self.entities = entities or []
        self.deployment_map = deployment_map or []
        self.diagnostics = diagnostics or BuildDiagnostics(orphan_fns=0, intg_skipped=0, intg_total_eligible=0)
        self.relationships = relationships or []
        self.deployment_nodes = deployment_nodes or []
        self.datastore_entity_links = datastore_entity_links or []
        self.subdomains = subdomains or []
        self.subdomain_systems = subdomain_systems or {}
        self.data_access = data_access or []
        self.sys_domain = sys_domain or {}
        self.archi_to_c4 = archi_to_c4 or {}
        self.promoted_archi_to_c4 = promoted_archi_to_c4 or {}
        self.promoted_parents = promoted_parents or {}
        self.iface_c4_path = iface_c4_path or {}
        self.tech_archi_to_c4 = tech_archi_to_c4 or {}
