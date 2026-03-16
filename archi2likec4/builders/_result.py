"""BuildResult NamedTuple — the output of the build phase."""

from typing import NamedTuple


class BuildResult(NamedTuple):
    systems: list
    integrations: list
    data_access: list
    entities: list
    domain_systems: dict
    sys_domain: dict
    archi_to_c4: dict
    promoted_archi_to_c4: dict
    promoted_parents: dict
    iface_c4_path: dict
    orphan_fns: int
    solution_views: list
    relationships: list
    domains_info: list  # original parsed DomainInfo list
    deployment_nodes: list
    deployment_map: list
    tech_archi_to_c4: dict
    datastore_entity_links: list
    intg_skipped: int
    intg_total_eligible: int
    subdomains: list  # list[Subdomain]
    subdomain_systems: dict  # (domain_folder, subdomain_c4_id) → list[system c4_id]
