"""Builders: domain and subdomain assignment."""

import logging
from typing import Any

from ..models import (
    DataAccess,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    Subdomain,
    System,
)

logger = logging.getLogger(__name__)


def _apply_domain_overrides(
    systems: list[System],
    domain_overrides: dict[str, str],
    result: dict[str, list[System]],
) -> list[System]:
    """Pass 0: apply explicit domain overrides (highest priority).

    Returns the list of systems that were NOT overridden (remaining).
    """
    override_ids: set[int] = set()
    for sys in systems:
        if sys.name in domain_overrides:
            target = domain_overrides[sys.name]
            if target not in result:
                result[target] = []
            sys.domain = target
            result[target].append(sys)
            override_ids.add(id(sys))
    return [s for s in systems if id(s) not in override_ids]


def _assign_by_view_membership(
    systems: list[System],
    id_to_domains: dict[str, list[str]],
    result: dict[str, list[System]],
) -> None:
    """Pass 1: assign domains by hit counting across view membership."""
    for sys in systems:
        all_ids: set[str] = set()
        if sys.archi_id:
            all_ids.add(sys.archi_id)
        all_ids.update(sys.extra_archi_ids)
        for sub in sys.subsystems:
            if sub.archi_id:
                all_ids.add(sub.archi_id)

        hits: dict[str, int] = {}
        for aid in all_ids:
            for domain_id in id_to_domains.get(aid, []):
                hits[domain_id] = hits.get(domain_id, 0) + 1

        if hits:
            primary = min(hits.items(), key=lambda x: (-x[1], x[0]))[0]
            sys.domain = primary
            result[primary].append(sys)
        else:
            sys.domain = 'unassigned'
            result['unassigned'].append(sys)


def _promote_children_domains(
    result: dict[str, list[System]],
    promote_children: dict[str, str],
) -> None:
    """Pass 2: fallback domain for promoted children."""
    still_unassigned: list[System] = []
    for sys in result['unassigned']:
        parent_prefix = sys.name.split('.', 1)[0]
        if parent_prefix in promote_children:
            fallback = promote_children[parent_prefix]
            if fallback not in result:
                result[fallback] = []
            sys.domain = fallback
            result[fallback].append(sys)
        else:
            still_unassigned.append(sys)
    result['unassigned'] = still_unassigned


def _apply_extra_patterns(
    result: dict[str, list[System]],
    extra_domain_patterns: list[dict[str, Any]],
) -> None:
    """Pass 3: assign unassigned systems to extra domains via pattern matching."""
    for extra in extra_domain_patterns:
        extra_id = extra['c4_id']
        patterns_lower = [p.lower() for p in extra['patterns']]
        if extra_id not in result:
            result[extra_id] = []

        still_unassigned: list[System] = []
        for sys in result['unassigned']:
            name_lower = sys.name.lower()
            matched = any(p in name_lower for p in patterns_lower)
            if matched:
                sys.domain = extra_id
                result[extra_id].append(sys)
            else:
                still_unassigned.append(sys)
        result['unassigned'] = still_unassigned


def assign_domains(
    systems: list[System],
    domains: list[DomainInfo],
    promote_children: dict[str, str] | None = None,
    extra_domain_patterns: list[dict[str, Any]] | None = None,
    domain_overrides: dict[str, str] | None = None,
) -> dict[str, list[System]]:
    """Assign each system to a primary domain based on view membership."""
    id_to_domains: dict[str, list[str]] = {}
    for domain in domains:
        for aid in domain.archi_ids:
            id_to_domains.setdefault(aid, []).append(domain.c4_id)

    result: dict[str, list[System]] = {d.c4_id: [] for d in domains}
    result['unassigned'] = []

    remaining = list(systems)
    if domain_overrides:
        remaining = _apply_domain_overrides(systems, domain_overrides, result)

    _assign_by_view_membership(remaining, id_to_domains, result)
    _promote_children_domains(result, promote_children or {})
    _apply_extra_patterns(result, extra_domain_patterns or [])

    return result


def _build_subdomain_lookup(
    parsed_subdomains: list[ParsedSubdomain],
) -> tuple[dict[str, list[ParsedSubdomain]], dict[tuple[str, str], ParsedSubdomain]]:
    """Build lookup tables for subdomain assignment.

    Returns (archi_to_psds, sd_id_to_psd):
    - archi_to_psds: archi_id → list[ParsedSubdomain] (component membership index)
    - sd_id_to_psd: (domain_folder, subdomain_archi_id) → ParsedSubdomain (domain-scoped index)
    """
    archi_to_psds: dict[str, list[ParsedSubdomain]] = {}
    sd_id_to_psd: dict[tuple[str, str], ParsedSubdomain] = {}
    for psd in parsed_subdomains:
        for cid in psd.component_ids:
            if cid in archi_to_psds:
                existing_names = [p.name for p in archi_to_psds[cid]]
                logger.warning(
                    'Component %s appears in multiple subdomain folders: %r and %r '
                    '— all candidates kept; check your model for duplicate assignments.',
                    cid, existing_names, psd.name,
                )
            archi_to_psds.setdefault(cid, []).append(psd)
        sd_id_to_psd[(psd.domain_folder, psd.archi_id)] = psd
    return archi_to_psds, sd_id_to_psd


def _assign_subdomain_by_folder(
    sys: System,
    archi_to_psds: dict[str, list[ParsedSubdomain]],
) -> ParsedSubdomain | None:
    """Try to match a system to a subdomain via its primary and extra archi_ids.

    Checks the system's own archi_id and extra_archi_ids (from merged duplicates).
    Returns the first same-domain ParsedSubdomain match, or None.
    """
    primary_ids: list[str] = []
    if sys.archi_id:
        primary_ids.append(sys.archi_id)
    primary_ids.extend(sys.extra_archi_ids)

    for aid in primary_ids:
        candidates = archi_to_psds.get(aid)
        if not candidates:
            continue
        for candidate in candidates:
            if sys.domain == candidate.domain_folder:
                return candidate
    return None


def _assign_subdomain_by_majority_vote(
    sys: System,
    archi_to_psds: dict[str, list[ParsedSubdomain]],
) -> ParsedSubdomain | None:
    """Fall back to subsystem archi_ids using majority-vote.

    When the system itself is not listed in any subdomain view but its child
    components are, count hits per subdomain and pick the winner.
    Ties are broken alphabetically by subdomain archi_id.
    Returns the winning ParsedSubdomain, or None.
    """
    if not sys.subsystems:
        return None

    sub_hits: dict[tuple[str, str], int] = {}
    psd_by_key: dict[tuple[str, str], ParsedSubdomain] = {}
    for sub in sys.subsystems:
        if not sub.archi_id:
            continue
        sub_candidates = archi_to_psds.get(sub.archi_id)
        if not sub_candidates:
            continue
        for candidate in sub_candidates:
            if sys.domain == candidate.domain_folder:
                key = (candidate.domain_folder, candidate.archi_id)
                sub_hits[key] = sub_hits.get(key, 0) + 1
                psd_by_key[key] = candidate

    if not sub_hits:
        return None

    best_key = min(sub_hits.items(), key=lambda x: (-x[1], x[0][1]))[0]
    return psd_by_key[best_key]


def _apply_collision_guard(
    systems: list[System],
    parsed_subdomains: list[ParsedSubdomain],
    sd_id_to_psd: dict[tuple[str, str], ParsedSubdomain],
    subdomains_by_key: dict[tuple[str, str], Subdomain],
    subdomain_systems: dict[tuple[str, str], list[str]],
) -> None:
    """Auto-assign systems whose c4_id collides with a subdomain c4_id in the same domain.

    Without this, a system named "AIM" and a subdomain folder also named "AIM"
    would both generate ``aim = ...`` at the domain level, causing a LikeC4
    duplicate-element-name error.
    """
    domain_sd_ids: dict[str, set[str]] = {}
    for psd in parsed_subdomains:
        domain_sd_ids.setdefault(psd.domain_folder, set()).add(psd.archi_id)

    for sys in systems:
        if sys.subdomain or not sys.domain:
            continue
        if sys.c4_id not in domain_sd_ids.get(sys.domain, set()):
            continue
        matched_psd = sd_id_to_psd.get((sys.domain, sys.c4_id))
        if matched_psd is None:
            continue
        sd_key = (matched_psd.domain_folder, matched_psd.archi_id)
        if sd_key not in subdomains_by_key:
            subdomains_by_key[sd_key] = Subdomain(
                c4_id=matched_psd.archi_id,
                name=matched_psd.name,
                domain_id=matched_psd.domain_folder,
                system_ids=[],
            )
        sys.subdomain = matched_psd.archi_id
        subdomains_by_key[sd_key].system_ids.append(sys.c4_id)
        subdomain_systems.setdefault(sd_key, []).append(sys.c4_id)
        logger.info(
            'Collision guard: system %r auto-assigned to subdomain %r (same c4_id)',
            sys.c4_id, matched_psd.archi_id,
        )


def _register_subdomain_match(
    sys: System,
    matched_psd: ParsedSubdomain,
    subdomains_by_key: dict[tuple[str, str], Subdomain],
    subdomain_systems: dict[tuple[str, str], list[str]],
) -> None:
    """Register a matched system→subdomain assignment in the result structures."""
    sd_key = (matched_psd.domain_folder, matched_psd.archi_id)
    if sd_key not in subdomains_by_key:
        subdomains_by_key[sd_key] = Subdomain(
            c4_id=matched_psd.archi_id,
            name=matched_psd.name,
            domain_id=matched_psd.domain_folder,
            system_ids=[],
        )
    sys.subdomain = matched_psd.archi_id
    subdomains_by_key[sd_key].system_ids.append(sys.c4_id)
    subdomain_systems.setdefault(sd_key, []).append(sys.c4_id)


def assign_subdomains(
    systems: list[System],
    parsed_subdomains: list[ParsedSubdomain],
    manual_overrides: dict[str, str] | None = None,
) -> tuple[list[Subdomain], dict[tuple[str, str], list[str]]]:
    """Assign each system to a subdomain (Pass 4 of hierarchy assignment).

    Checks if any archi_id of a system appears in a ParsedSubdomain's
    component_ids list. Sets system.subdomain to the matched subdomain c4_id.

    ``manual_overrides`` maps system *name* → subdomain c4_id and takes
    precedence over folder-based auto-detection.  The referenced subdomain
    must already exist in *parsed_subdomains*.

    Returns (subdomains, subdomain_systems) where subdomain_systems maps
    (domain_folder, subdomain_c4_id) → list of system c4_ids.
    """
    archi_to_psds, sd_id_to_psd = _build_subdomain_lookup(parsed_subdomains)

    subdomain_systems: dict[tuple[str, str], list[str]] = {}
    subdomains_by_key: dict[tuple[str, str], Subdomain] = {}

    # Build name → system index for manual overrides
    sys_by_name: dict[str, System] = {s.name: s for s in systems} if manual_overrides else {}
    # Set of system c4_ids that have a valid manual override
    override_sys_ids: set[str] = set()
    if manual_overrides:
        for sys_name, sd_c4_id in manual_overrides.items():
            target = sys_by_name.get(sys_name)
            if target is None:
                continue
            if (target.domain or '', sd_c4_id) in sd_id_to_psd:
                override_sys_ids.add(target.c4_id)

    for sys in systems:
        if not sys.domain:
            continue

        matched_psd: ParsedSubdomain | None = None

        if manual_overrides and sys.c4_id in override_sys_ids:
            override_sd_id = manual_overrides.get(sys.name)
            if override_sd_id:
                matched_psd = sd_id_to_psd.get((sys.domain or '', override_sd_id))
        else:
            matched_psd = _assign_subdomain_by_folder(sys, archi_to_psds)
            if matched_psd is None:
                matched_psd = _assign_subdomain_by_majority_vote(sys, archi_to_psds)

        if matched_psd is None or sys.domain != matched_psd.domain_folder:
            continue

        _register_subdomain_match(sys, matched_psd, subdomains_by_key, subdomain_systems)

    _apply_collision_guard(systems, parsed_subdomains, sd_id_to_psd, subdomains_by_key, subdomain_systems)

    subdomains = sorted(subdomains_by_key.values(), key=lambda s: (s.domain_id, s.c4_id))
    return subdomains, subdomain_systems


def apply_domain_prefix(
    integrations: list[Integration],
    data_access: list[DataAccess],
    sys_domain: dict[str, str],
    sys_subdomain: dict[str, str] | None = None,
) -> None:
    """Add domain (and optional subdomain) prefix to integration and data access paths.

    Transforms 'efs' → 'channels.efs' (no subdomain) or
    'efs' → 'channels.banking.efs' (with subdomain) based on assignment.
    """
    def _prefix(sys_c4_id: str) -> str:
        domain = sys_domain.get(sys_c4_id, 'unassigned')
        subdomain = sys_subdomain.get(sys_c4_id, '') if sys_subdomain else ''
        if subdomain:
            return f'{domain}.{subdomain}.{sys_c4_id}'
        return f'{domain}.{sys_c4_id}'

    for intg in integrations:
        intg.source_path = _prefix(intg.source_path)
        intg.target_path = _prefix(intg.target_path)

    for da in data_access:
        da.system_path = _prefix(da.system_path)
