"""Tests for maturity GAP detectors."""

from archi2likec4.maturity.detectors import (
    detect_all_gaps,
    detect_gap_deploy,
    detect_gap_desc,
    detect_gap_domain,
    detect_gap_dup,
    detect_gap_integ,
    detect_gap_orphan,
    detect_gap_ref,
    detect_gap_shallow,
)
from archi2likec4.maturity.gaps import GapCode, Severity
from archi2likec4.models import DeploymentNode, Integration, System
from tests.helpers import MockBuilt, MockConfig


def _sys(c4_id: str, name: str = '', **kw) -> System:
    return System(c4_id=c4_id, name=name or c4_id, archi_id=f'a-{c4_id}', **kw)


def _node(c4_id: str, kind: str = 'vm') -> DeploymentNode:
    return DeploymentNode(c4_id=c4_id, name=c4_id, archi_id=f't-{c4_id}', tech_type='Node', kind=kind)


class TestGapDeploy:
    def test_no_gap_when_no_deployment(self):
        built = MockBuilt(systems=[_sys('s1')], deployment_nodes=[])
        assert detect_gap_deploy(built, MockConfig()) == []

    def test_gap_when_system_not_mapped(self):
        built = MockBuilt(
            systems=[_sys('s1')],
            deployment_nodes=[_node('srv1')],
            deployment_map=[],
        )
        gaps = detect_gap_deploy(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.DEPLOY
        assert gaps[0].severity == Severity.BLOCKER

    def test_no_gap_when_system_mapped(self):
        built = MockBuilt(
            systems=[_sys('s1')],
            deployment_nodes=[_node('srv1')],
            deployment_map=[('dom.s1.api', 'prod.srv1')],
        )
        gaps = detect_gap_deploy(built, MockConfig())
        assert gaps == []


class TestGapDomain:
    def test_gap_for_unassigned(self):
        s = _sys('s1')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        gaps = detect_gap_domain(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.DOMAIN

    def test_no_gap_when_assigned(self):
        s = _sys('s1')
        built = MockBuilt(
            systems=[s],
            domain_systems={'channels': [s]},
        )
        assert detect_gap_domain(built, MockConfig()) == []


class TestGapInteg:
    def test_gap_when_no_integrations(self):
        built = MockBuilt(systems=[_sys('s1')], integrations=[])
        gaps = detect_gap_integ(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.INTEG

    def test_no_gap_when_has_integrations(self):
        intg = Integration(source_path='dom.s1.api', target_path='dom.s2.api', name='call', rel_type='Flow')
        built = MockBuilt(
            systems=[_sys('s1'), _sys('s2')],
            integrations=[intg],
        )
        gaps = detect_gap_integ(built, MockConfig())
        assert gaps == []


class TestGapShallow:
    def test_gap_when_no_children(self):
        built = MockBuilt(systems=[_sys('s1')])
        gaps = detect_gap_shallow(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.SHALLOW

    def test_no_gap_when_has_subsystems(self):
        from archi2likec4.models import Subsystem
        s = _sys('s1')
        s.subsystems = [Subsystem(c4_id='sub1', name='Sub1', archi_id='a-sub1')]
        built = MockBuilt(systems=[s])
        gaps = detect_gap_shallow(built, MockConfig())
        assert gaps == []


class TestGapDup:
    def test_gap_when_duplicate_names(self):
        built = MockBuilt(systems=[_sys('s1', name='SameName'), _sys('s2', name='SameName')])
        gaps = detect_gap_dup(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.DUP
        assert gaps[0].severity == Severity.BLOCKER

    def test_no_gap_when_unique_names(self):
        built = MockBuilt(systems=[_sys('s1', name='Sys1'), _sys('s2', name='Sys2')])
        assert detect_gap_dup(built, MockConfig()) == []


class TestGapDesc:
    def test_gap_when_no_docs(self):
        built = MockBuilt(systems=[_sys('s1')])
        gaps = detect_gap_desc(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.DESC

    def test_no_gap_when_has_docs(self):
        s = _sys('s1')
        s.documentation = 'This system handles payments.'
        built = MockBuilt(systems=[s])
        assert detect_gap_desc(built, MockConfig()) == []


class TestGapRef:
    def test_gap_for_broken_target(self):
        intg = Integration(source_path='dom.s1', target_path='dom.nonexistent', name='x', rel_type='Flow')
        built = MockBuilt(
            systems=[_sys('s1')],
            integrations=[intg],
            domain_systems={'dom': [_sys('s1')]},
        )
        gaps = detect_gap_ref(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.REF

    def test_no_gap_for_valid_target(self):
        s1, s2 = _sys('s1'), _sys('s2')
        intg = Integration(source_path='dom.s1', target_path='dom.s2', name='x', rel_type='Flow')
        built = MockBuilt(
            systems=[s1, s2],
            integrations=[intg],
            domain_systems={'dom': [s1, s2]},
        )
        assert detect_gap_ref(built, MockConfig()) == []


class TestGapOrphan:
    def test_gap_for_unused_vm(self):
        built = MockBuilt(
            deployment_nodes=[_node('vm1')],
            deployment_map=[],
        )
        gaps = detect_gap_orphan(built, MockConfig())
        assert len(gaps) == 1
        assert gaps[0].code == GapCode.ORPHAN

    def test_no_gap_when_vm_used(self):
        built = MockBuilt(
            deployment_nodes=[_node('vm1')],
            deployment_map=[('dom.s1', 'prod.vm1')],
        )
        assert detect_gap_orphan(built, MockConfig()) == []


class TestDetectAllGaps:
    def test_returns_sorted_by_severity(self):
        s = _sys('s1')
        built = MockBuilt(
            systems=[s],
            deployment_nodes=[_node('vm1')],
            deployment_map=[],
            domain_systems={'unassigned': [s]},
        )
        gaps = detect_all_gaps(built, MockConfig())
        severities = [g.severity for g in gaps]
        # Blockers first, then degraded, then cosmetic
        assert severities == sorted(severities, key=lambda s: {
            Severity.BLOCKER: 0, Severity.DEGRADED: 1, Severity.COSMETIC: 2,
        }.get(s, 9))
