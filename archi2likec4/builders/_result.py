"""BuildResult NamedTuple — the output of the build phase."""

from typing import NamedTuple

from ..models import (
    DataAccess,
    DataEntity,
    DeploymentNode,
    DomainInfo,
    Integration,
    RawRelationship,
    SolutionView,
    Subdomain,
    System,
)


class BuildResult(NamedTuple):
    """Complete output of the build phase — passed to generators."""

    systems: list[System]
    integrations: list[Integration]
    data_access: list[DataAccess]
    entities: list[DataEntity]
    domain_systems: dict[str, list[System]]
    sys_domain: dict[str, str]
    archi_to_c4: dict[str, str]
    promoted_archi_to_c4: dict[str, list[str]]
    promoted_parents: dict[str, list[str]]
    iface_c4_path: dict[str, str]
    orphan_fns: int
    solution_views: list[SolutionView]
    relationships: list[RawRelationship]
    domains_info: list[DomainInfo]
    deployment_nodes: list[DeploymentNode]
    deployment_map: list[tuple[str, str]]
    tech_archi_to_c4: dict[str, str]
    datastore_entity_links: list[tuple[str, str]]
    intg_skipped: int
    intg_total_eligible: int
    subdomains: list[Subdomain]
    subdomain_systems: dict[tuple[str, str], list[str]]
