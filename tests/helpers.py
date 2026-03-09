"""Shared mock objects for tests."""


class MockConfig:
    """Minimal config mock for audit/generator tests."""
    def __init__(self, promote_children=None, promote_warn_threshold=10,
                 audit_suppress=None, audit_suppress_incidents=None,
                 domain_overrides=None, reviewed_systems=None):
        self.promote_children = promote_children or {}
        self.promote_warn_threshold = promote_warn_threshold
        self.audit_suppress = audit_suppress or []
        self.audit_suppress_incidents = audit_suppress_incidents or []
        self.domain_overrides = domain_overrides or {}
        self.reviewed_systems = reviewed_systems or []


class MockBuilt:
    """Minimal BuildResult mock."""
    def __init__(self, systems=None, domain_systems=None, integrations=None,
                 entities=None, deployment_map=None, orphan_fns=0,
                 relationships=None, deployment_nodes=None,
                 datastore_entity_links=None):
        self.systems = systems or []
        self.domain_systems = domain_systems or {}
        self.integrations = integrations or []
        self.entities = entities or []
        self.deployment_map = deployment_map or []
        self.orphan_fns = orphan_fns
        self.relationships = relationships or []
        self.deployment_nodes = deployment_nodes or []
        self.datastore_entity_links = datastore_entity_links or []
