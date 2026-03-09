"""Tests for archi2likec4.audit_data module."""

from archi2likec4.audit_data import AuditSummary, AuditIncident, compute_audit_incidents
from archi2likec4.models import System, RawRelationship


class _MockConfig:
    """Minimal config mock for audit_data tests."""
    def __init__(self, promote_children=None, promote_warn_threshold=10,
                 audit_suppress=None, audit_suppress_incidents=None):
        self.promote_children = promote_children or {}
        self.promote_warn_threshold = promote_warn_threshold
        self.audit_suppress = audit_suppress or []
        self.audit_suppress_incidents = audit_suppress_incidents or []


class _MockBuilt:
    """Minimal BuildResult mock."""
    def __init__(self, systems=None, domain_systems=None, integrations=None,
                 entities=None, deployment_map=None, orphan_fns=0,
                 relationships=None):
        self.systems = systems or []
        self.domain_systems = domain_systems or {}
        self.integrations = integrations or []
        self.entities = entities or []
        self.deployment_map = deployment_map or []
        self.orphan_fns = orphan_fns
        self.relationships = relationships or []


class TestComputeAuditIncidents:
    def test_returns_summary(self):
        s1 = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = _MockBuilt(systems=[s1])
        summary, incidents = compute_audit_incidents(built, 0, 0, _MockConfig())
        assert isinstance(summary, AuditSummary)
        assert summary.total_systems == 1
        assert summary.total_subsystems == 0

    def test_qa1_unassigned(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        s2 = System(c4_id='efs', name='EFS', archi_id='s2', metadata={}, domain='channels')
        built = _MockBuilt(
            systems=[s1, s2],
            domain_systems={'unassigned': [s1], 'channels': [s2]},
        )
        summary, incidents = compute_audit_incidents(built, 0, 0, _MockConfig())
        qa1 = next((i for i in incidents if i.qa_id == 'QA-1'), None)
        assert qa1 is not None
        assert qa1.severity == 'Critical'
        assert qa1.count == 1
        assert qa1.affected[0]['name'] == 'AD'

    def test_suppress_filters_systems(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = _MockBuilt(
            systems=[s1],
            domain_systems={'unassigned': [s1]},
        )
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              _MockConfig(audit_suppress=['AD']))
        qa1 = next((i for i in incidents if i.qa_id == 'QA-1'), None)
        # AD is suppressed, so QA-1 should be absent (all items suppressed)
        assert qa1 is None

    def test_suppress_incidents_marks_suppressed(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = _MockBuilt(
            systems=[s1],
            domain_systems={'unassigned': [s1]},
        )
        _, incidents = compute_audit_incidents(
            built, 0, 0,
            _MockConfig(audit_suppress_incidents=['QA-1']),
        )
        qa1 = next((i for i in incidents if i.qa_id == 'QA-1'), None)
        assert qa1 is not None
        assert qa1.suppressed is True
        assert qa1.count == 1

    def test_empty_model_no_incidents(self):
        built = _MockBuilt()
        summary, incidents = compute_audit_incidents(built, 0, 0, _MockConfig())
        assert summary.total_systems == 0
        assert incidents == []

    def test_qa7_lost_integrations(self):
        s1 = System(c4_id='a', name='A', archi_id='s1', metadata={}, domain='d1')
        rels = [
            RawRelationship(rel_id='r1', rel_type='FlowRelationship',
                            name='flow', source_type='AC', source_id='src',
                            target_type='AC', target_id='tgt'),
        ]
        built = _MockBuilt(
            systems=[s1],
            integrations=[],  # 0 resolved
            relationships=rels,
        )
        _, incidents = compute_audit_incidents(built, 0, 0, _MockConfig())
        qa7 = next((i for i in incidents if i.qa_id == 'QA-7'), None)
        assert qa7 is not None
        assert qa7.severity == 'Critical'
        assert qa7.count == 1
