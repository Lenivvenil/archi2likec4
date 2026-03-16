"""Shared mock objects for tests."""


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


class MockBuilt:
    """Mock for BuildResult — all fields with defaults."""
    def __init__(
        self,
        systems=None,
        domain_systems=None,
        integrations=None,
        entities=None,
        deployment_map=None,
        orphan_fns=0,
        relationships=None,
        deployment_nodes=None,
        datastore_entity_links=None,
        intg_skipped=0,
        intg_total_eligible=0,
        subdomains=None,
        subdomain_systems=None,
        # Additional BuildResult fields
        data_access=None,
        sys_domain=None,
        archi_to_c4=None,
        promoted_archi_to_c4=None,
        promoted_parents=None,
        iface_c4_path=None,
        solution_views=None,
        domains_info=None,
        tech_archi_to_c4=None,
    ):
        self.systems = systems or []
        self.domain_systems = domain_systems or {}
        self.integrations = integrations or []
        self.entities = entities or []
        self.deployment_map = deployment_map or []
        self.orphan_fns = orphan_fns
        self.relationships = relationships or []
        self.deployment_nodes = deployment_nodes or []
        self.datastore_entity_links = datastore_entity_links or []
        self.intg_skipped = intg_skipped
        self.intg_total_eligible = intg_total_eligible
        self.subdomains = subdomains or []
        self.subdomain_systems = subdomain_systems or {}
        self.data_access = data_access or []
        self.sys_domain = sys_domain or {}
        self.archi_to_c4 = archi_to_c4 or {}
        self.promoted_archi_to_c4 = promoted_archi_to_c4 or {}
        self.promoted_parents = promoted_parents or {}
        self.iface_c4_path = iface_c4_path or {}
        self.solution_views = solution_views or []
        self.domains_info = domains_info or []
        self.tech_archi_to_c4 = tech_archi_to_c4 or {}
