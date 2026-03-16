"""Builders: domain and subdomain assignment."""

import logging

from ..models import (
    DataAccess,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    Subdomain,
    System,
)

logger = logging.getLogger('archi2likec4')


def assign_domains(  # noqa: C901
    systems: list[System],
    domains: list[DomainInfo],
    promote_children: dict[str, str] | None = None,
    extra_domain_patterns: list[dict] | None = None,
    domain_overrides: dict[str, str] | None = None,
) -> dict[str, list[System]]:
    """Assign each system to a primary domain based on view membership."""
    # Reverse map: archi_id → [(domain_c4_id, ...)]
    id_to_domains: dict[str, list[str]] = {}
    for domain in domains:
        for aid in domain.archi_ids:
            id_to_domains.setdefault(aid, []).append(domain.c4_id)

    result: dict[str, list[System]] = {d.c4_id: [] for d in domains}
    result['unassigned'] = []

    # Pass 0: explicit domain overrides (highest priority)
    remaining = list(systems)
    if domain_overrides:
        override_ids: set[int] = set()
        for sys in systems:
            if sys.name in domain_overrides:
                target = domain_overrides[sys.name]
                if target not in result:
                    result[target] = []
                sys.domain = target
                result[target].append(sys)
                override_ids.add(id(sys))
        remaining = [s for s in systems if id(s) not in override_ids]

    for sys in remaining:
        # Collect archi IDs for this system (system + duplicates + all subsystems)
        all_ids: set[str] = set()
        if sys.archi_id:
            all_ids.add(sys.archi_id)
        all_ids.update(sys.extra_archi_ids)
        for sub in sys.subsystems:
            if sub.archi_id:
                all_ids.add(sub.archi_id)

        # Count hits per domain
        hits: dict[str, int] = {}
        for aid in all_ids:
            for domain_id in id_to_domains.get(aid, []):
                hits[domain_id] = hits.get(domain_id, 0) + 1

        if hits:
            # Primary = domain with most hits; ties broken alphabetically (smallest id first)
            primary = min(hits.items(), key=lambda x: (-x[1], x[0]))[0]
            sys.domain = primary
            result[primary].append(sys)
        else:
            sys.domain = 'unassigned'
            result['unassigned'].append(sys)

    # Second pass: fallback domain for promoted children
    if promote_children is None:
        promote_children = {}
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

    # Third pass: assign unassigned systems to extra domains via pattern matching
    if extra_domain_patterns is None:
        extra_domain_patterns = []
    for extra in extra_domain_patterns:
        extra_id = extra['c4_id']
        patterns_lower = [p.lower() for p in extra['patterns']]
        if extra_id not in result:
            result[extra_id] = []

        still_unassigned = []
        for sys in result['unassigned']:
            name_lower = sys.name.lower()
            matched = any(p in name_lower for p in patterns_lower)
            if matched:
                sys.domain = extra_id
                result[extra_id].append(sys)
            else:
                still_unassigned.append(sys)
        result['unassigned'] = still_unassigned

    return result


def assign_subdomains(  # noqa: C901
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
    # Build archi_id → ParsedSubdomain index
    archi_to_psd: dict[str, ParsedSubdomain] = {}
    # Build (domain_folder, subdomain_archi_id) → ParsedSubdomain index for manual overrides.
    # Keyed by domain to avoid cross-domain collisions when two domains share the same
    # subdomain id (e.g. channels/core and products/core).
    sd_id_to_psd: dict[tuple[str, str], ParsedSubdomain] = {}
    for psd in parsed_subdomains:
        for cid in psd.component_ids:
            archi_to_psd[cid] = psd
        sd_id_to_psd[(psd.domain_folder, psd.archi_id)] = psd

    subdomain_systems: dict[tuple[str, str], list[str]] = {}
    subdomains_by_key: dict[tuple[str, str], Subdomain] = {}

    # Build name → system index for manual overrides
    sys_by_name: dict[str, System] = {s.name: s for s in systems} if manual_overrides else {}
    # Set of system c4_ids that have a manual override (skip auto-detection for these)
    override_sys_ids: set[str] = set()
    if manual_overrides:
        for sys_name, sd_c4_id in manual_overrides.items():
            target = sys_by_name.get(sys_name)
            if target is None:
                continue
            # Only register as override when the target subdomain actually exists.
            # If the subdomain id is invalid, fall through to auto-detection instead
            # of silently clearing the system's subdomain assignment.
            if (target.domain or '', sd_c4_id) in sd_id_to_psd:
                override_sys_ids.add(target.c4_id)

    for sys in systems:
        if not sys.domain:
            # Unassigned systems have no domain context — cannot belong to a subdomain.
            continue

        matched_psd: ParsedSubdomain | None = None

        if manual_overrides and sys.c4_id in override_sys_ids:
            # Manual override takes precedence over folder-based detection.
            # Look up by (domain, subdomain_id) to avoid cross-domain collisions.
            override_sd_id = manual_overrides.get(sys.name)
            if override_sd_id:
                matched_psd = sd_id_to_psd.get((sys.domain or '', override_sd_id))
        else:
            # Collect all archi_ids for this system
            all_ids: list[str] = []
            if sys.archi_id:
                all_ids.append(sys.archi_id)
            all_ids.extend(sys.extra_archi_ids)

            # Find matching subdomain - keep searching until a same-domain
            # candidate is found.  A merged system may carry extra_archi_ids
            # from a foreign domain; the first hit might therefore belong to
            # the wrong domain, so we must not stop at the first match.
            for aid in all_ids:
                candidate = archi_to_psd.get(aid)
                if candidate is None:
                    continue
                if sys.domain != candidate.domain_folder:
                    continue
                matched_psd = candidate
                break

        if matched_psd is None:
            continue

        # Safety-net: manual-override path already uses domain-scoped lookup,
        # but guard here as well in case future paths slip through.
        if sys.domain != matched_psd.domain_folder:
            continue

        # Key by (domain_folder, archi_id) to avoid cross-domain collisions
        sd_key = (matched_psd.domain_folder, matched_psd.archi_id)
        if sd_key not in subdomains_by_key:
            subdomains_by_key[sd_key] = Subdomain(
                c4_id=matched_psd.archi_id,
                name=matched_psd.name,
                domain_id=matched_psd.domain_folder,
                system_ids=[],
            )

        # Assign system to subdomain
        sys.subdomain = matched_psd.archi_id
        subdomains_by_key[sd_key].system_ids.append(sys.c4_id)
        subdomain_systems.setdefault(sd_key, []).append(sys.c4_id)

    # Collision guard: if an unassigned system's c4_id equals a subdomain c4_id
    # in the same domain, auto-assign it to that subdomain.  Without this a
    # system named "AIM" and a subdomain folder also named "AIM" would both
    # generate ``aim = ...`` at the domain level, causing a LikeC4 duplicate-
    # element-name error.
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
