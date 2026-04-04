"""GAP detectors: 10 functions that detect architectural gaps from BuildResult."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from .gaps import Gap, GapCode, Severity

if TYPE_CHECKING:
    from ..builders._result import BuildResult
    from ..config import ConvertConfig

logger = logging.getLogger(__name__)


def detect_gap_deploy(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-DEPLOY: System not deployed to any infrastructure node."""
    mapped_systems: set[str] = set()
    if built.deployment_map:
        for app_path, _ in built.deployment_map:
            # Extract system c4_id from path like 'domain.system.subsystem'
            parts = app_path.split('.')
            if len(parts) >= 2:
                mapped_systems.add(parts[1])

    gaps: list[Gap] = []
    for sys in built.systems:
        if sys.c4_id not in mapped_systems and built.deployment_nodes:
            gaps.append(Gap(
                    code=GapCode.DEPLOY,
                    severity=Severity.BLOCKER,
                    element_id=sys.c4_id,
                    element_name=sys.name,
                    context={'subsystem_count': str(len(sys.subsystems))},
                    remediation='Add deployment mapping in ArchiMate or via extend in deployment.c4',
                ))
    return gaps


def detect_gap_zone(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-ZONE: System deployed only to Path/CommunicationNetwork (no real VM)."""
    from ..models import INSTANCE_ALLOWED_KINDS
    from ..utils import flatten_deployment_nodes

    if not built.deployment_map or not built.deployment_nodes:
        return []

    # Build node kind index
    node_kinds: dict[str, str] = {}
    for node in flatten_deployment_nodes(built.deployment_nodes):
        node_kinds[node.c4_id] = node.kind

    # Find systems where ALL mappings point to non-compute nodes
    sys_infra: dict[str, list[str]] = {}
    for app_path, infra_path in built.deployment_map:
        parts = app_path.split('.')
        if len(parts) >= 2:
            sys_id = parts[1]
            sys_infra.setdefault(sys_id, []).append(infra_path)

    gaps: list[Gap] = []
    sys_lookup = {s.c4_id: s for s in built.systems}
    for sys_id, infra_paths in sys_infra.items():
        all_non_compute = all(
            node_kinds.get(p.split('.')[-1], '') not in INSTANCE_ALLOWED_KINDS
            for p in infra_paths
        )
        if all_non_compute and sys_id in sys_lookup:
            sys = sys_lookup[sys_id]
            gaps.append(Gap(
                code=GapCode.ZONE,
                severity=Severity.BLOCKER,
                element_id=sys.c4_id,
                element_name=sys.name,
                context={'infra_kinds': ', '.join(sorted({
                    node_kinds.get(p.split('.')[-1], 'unknown') for p in infra_paths
                }))},
                remediation='Replace Path/CommunicationNetwork mapping with actual VM/server',
            ))
    return gaps


def detect_gap_domain(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-DOMAIN: System in unassigned domain."""
    gaps: list[Gap] = []
    for sys in built.domain_systems.get('unassigned', []):
        gaps.append(Gap(
            code=GapCode.DOMAIN,
            severity=Severity.DEGRADED,
            element_id=sys.c4_id,
            element_name=sys.name,
            remediation='Place system on a functional_areas/ diagram in Archi',
        ))
    return gaps


def detect_gap_integ(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-INTEG: System has no integrations (0 relationships)."""
    systems_with_integ: set[str] = set()
    for intg in built.integrations:
        parts = intg.source_path.split('.')
        if len(parts) >= 2:
            systems_with_integ.add(parts[1])
        parts = intg.target_path.split('.')
        if len(parts) >= 2:
            systems_with_integ.add(parts[1])

    gaps: list[Gap] = []
    for sys in built.systems:
        if sys.c4_id not in systems_with_integ:
            gaps.append(Gap(
                code=GapCode.INTEG,
                severity=Severity.DEGRADED,
                element_id=sys.c4_id,
                element_name=sys.name,
                remediation='Add relationships in ArchiMate connecting this system to others',
            ))
    return gaps


def detect_gap_shallow(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-SHALLOW: System has no subsystems and no functions."""
    gaps: list[Gap] = []
    for sys in built.systems:
        if not sys.subsystems and not sys.functions:
            gaps.append(Gap(
                code=GapCode.SHALLOW,
                severity=Severity.DEGRADED,
                element_id=sys.c4_id,
                element_name=sys.name,
                remediation='Break system into subsystems or define ApplicationFunctions in ArchiMate',
            ))
    return gaps


def detect_gap_orphan(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-ORPHAN: VM/server without any instanceOf."""
    from ..models import INSTANCE_ALLOWED_KINDS
    from ..utils import flatten_deployment_nodes

    if not built.deployment_nodes:
        return []

    # Collect all infra node paths that have instanceOf
    used_nodes: set[str] = set()
    for _, infra_path in built.deployment_map:
        # Last segment is the node c4_id
        used_nodes.add(infra_path.split('.')[-1])

    gaps: list[Gap] = []
    for node in flatten_deployment_nodes(built.deployment_nodes):
        if node.kind in INSTANCE_ALLOWED_KINDS and node.c4_id not in used_nodes:
            gaps.append(Gap(
                code=GapCode.ORPHAN,
                severity=Severity.COSMETIC,
                element_id=node.c4_id,
                element_name=node.name,
                context={'kind': node.kind},
                remediation='Assign applications to this node or remove if unused',
            ))
    return gaps


def detect_gap_dup(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-DUP: Duplicate system names across domains."""
    name_count: Counter[str] = Counter()
    name_systems: dict[str, list[str]] = {}
    for sys in built.systems:
        key = sys.name.lower().strip()
        name_count[key] += 1
        name_systems.setdefault(key, []).append(sys.c4_id)

    gaps: list[Gap] = []
    seen: set[str] = set()
    for sys in built.systems:
        key = sys.name.lower().strip()
        if name_count[key] > 1 and key not in seen:
            seen.add(key)
            gaps.append(Gap(
                code=GapCode.DUP,
                severity=Severity.BLOCKER,
                element_id=sys.c4_id,
                element_name=sys.name,
                context={'duplicates': ', '.join(name_systems[key])},
                remediation='Merge duplicate systems or rename for uniqueness',
            ))
    return gaps


def detect_gap_desc(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-DESC: System has no documentation."""
    gaps: list[Gap] = []
    for sys in built.systems:
        if not sys.documentation or not sys.documentation.strip():
            gaps.append(Gap(
                code=GapCode.DESC,
                severity=Severity.COSMETIC,
                element_id=sys.c4_id,
                element_name=sys.name,
                remediation='Add documentation in ArchiMate element properties',
            ))
    return gaps


def detect_gap_ref(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-REF: Integration targets a non-existent system path."""
    known_paths: set[str] = set(built.archi_to_c4.values())
    # Also add all system paths from domain_systems
    for domain_id, sys_list in built.domain_systems.items():
        for sys in sys_list:
            known_paths.add(f'{domain_id}.{sys.c4_id}')
            for sub in sys.subsystems:
                known_paths.add(f'{domain_id}.{sys.c4_id}.{sub.c4_id}')

    gaps: list[Gap] = []
    seen_targets: set[str] = set()
    for intg in built.integrations:
        if intg.target_path not in known_paths and intg.target_path not in seen_targets:
            seen_targets.add(intg.target_path)
            gaps.append(Gap(
                code=GapCode.REF,
                severity=Severity.BLOCKER,
                element_id=intg.target_path,
                element_name=intg.target_path,
                context={'source': intg.source_path, 'rel_type': intg.rel_type},
                remediation='Create the target system or remove the broken relationship',
            ))
    return gaps


def detect_gap_env(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """GAP-ENV: Mixed environments in deployment (dev/test nodes alongside prod)."""
    # Currently single-environment — flag if config says prod but node names suggest otherwise
    if not built.deployment_nodes:
        return []

    from ..utils import flatten_deployment_nodes

    env_keywords = {'dev', 'test', 'staging', 'uat', 'qa'}
    prod_env = config.deployment_env

    gaps: list[Gap] = []
    for node in flatten_deployment_nodes(built.deployment_nodes):
        name_lower = node.name.lower()
        for kw in env_keywords:
            if kw in name_lower and prod_env == 'prod':
                gaps.append(Gap(
                    code=GapCode.ENV,
                    severity=Severity.DEGRADED,
                    element_id=node.c4_id,
                    element_name=node.name,
                    context={'detected_env': kw, 'configured_env': prod_env},
                    remediation='Separate environments or rename node to remove ambiguity',
                ))
                break  # one gap per node
    return gaps


# Registry of all detectors
_DETECTORS = [
    detect_gap_deploy,
    detect_gap_zone,
    detect_gap_domain,
    detect_gap_integ,
    detect_gap_shallow,
    detect_gap_orphan,
    detect_gap_dup,
    detect_gap_desc,
    detect_gap_ref,
    detect_gap_env,
]


def detect_all_gaps(built: BuildResult, config: ConvertConfig) -> list[Gap]:
    """Run all 10 detectors, return combined gap list sorted by severity."""
    severity_order = {Severity.BLOCKER: 0, Severity.DEGRADED: 1, Severity.COSMETIC: 2}
    all_gaps: list[Gap] = []
    for detector in _DETECTORS:
        all_gaps.extend(detector(built, config))
    all_gaps.sort(key=lambda g: (severity_order.get(g.severity, 9), g.code, g.element_id))
    return all_gaps
