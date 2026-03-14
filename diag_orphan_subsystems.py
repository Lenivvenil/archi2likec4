#!/usr/bin/env python3
"""Diagnostic: analyze unassigned systems to find orphaned subsystems.

Many "unassigned" systems may actually be subsystems that broke free from
their parent system because:
  1. Their ArchiMate name contains a dot (e.g., "EFS.Something") but the
     parent prefix is not in promote_children and the parent AC doesn't exist.
  2. They have CompositionRelationship pointing to an assigned parent.
  3. Their name prefix-matches a system in an assigned domain.
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path

# Ensure the project is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from archi2likec4.config import load_config
from archi2likec4.pipeline import _parse, _build

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


def main():
    config_path = Path('.archi2likec4.yaml')
    config = load_config(config_path)
    config.model_root = Path('architectural_repository/model').resolve()

    print("=" * 80)
    print("ORPHAN SUBSYSTEM DIAGNOSTIC")
    print("=" * 80)

    # Phase 1: Parse
    parsed = _parse(config.model_root, config)

    # Phase 2: Build
    built = _build(parsed, config)

    # -- Gather data --
    unassigned = built.domain_systems.get('unassigned', [])
    assigned_systems = []
    for domain_id, sys_list in built.domain_systems.items():
        if domain_id != 'unassigned':
            assigned_systems.extend(sys_list)

    print(f"\nTotal systems: {len(built.systems)}")
    print(f"Assigned systems: {len(assigned_systems)}")
    print(f"Unassigned systems: {len(unassigned)}")

    # Build lookup: archi_id -> System (for assigned systems)
    assigned_by_archi = {}
    for s in assigned_systems:
        if s.archi_id:
            assigned_by_archi[s.archi_id] = s
        for eid in s.extra_archi_ids:
            assigned_by_archi[eid] = s
        for sub in s.subsystems:
            if sub.archi_id:
                assigned_by_archi[sub.archi_id] = s

    # Build lookup: name -> (System, domain)
    assigned_by_name = {}
    for s in assigned_systems:
        assigned_by_name[s.name] = (s, s.domain)

    # Build composition relationships: child_archi_id -> parent_archi_id
    comp_child_to_parent = {}  # child -> parent (AC->AC compositions)
    for rel in parsed.relationships:
        if rel.rel_type == 'CompositionRelationship':
            if rel.source_type == 'ApplicationComponent' and rel.target_type == 'ApplicationComponent':
                comp_child_to_parent[rel.target_id] = rel.source_id

    # Build AppComponent lookup by archi_id for name resolution
    ac_by_id = {ac.archi_id: ac for ac in parsed.components}

    # -- Categorize unassigned systems --
    orphans = []       # likely orphaned subsystems
    standalone = []    # no parent evidence
    platform_cand = [] # match platform patterns

    platform_patterns = set()
    for extra in config.extra_domain_patterns:
        if extra['c4_id'] == 'platform':
            for p in extra['patterns']:
                platform_patterns.add(p.lower())

    for sys in unassigned:
        evidence = {}

        # Check 1: Does the name contain a dot?
        has_dot = '.' in sys.name.rstrip('.')
        if has_dot:
            prefix = sys.name.split('.', 1)[0]
            evidence['dot_prefix'] = prefix

        # Check 2: CompositionRelationship to an assigned parent?
        parent_archi_id = comp_child_to_parent.get(sys.archi_id)
        if parent_archi_id and parent_archi_id in assigned_by_archi:
            parent_sys = assigned_by_archi[parent_archi_id]
            evidence['composition_parent'] = f"{parent_sys.name} (domain: {parent_sys.domain})"

        # Also check if any of extra_archi_ids have composition parents
        for eid in sys.extra_archi_ids:
            pid = comp_child_to_parent.get(eid)
            if pid and pid in assigned_by_archi:
                parent_sys = assigned_by_archi[pid]
                evidence['composition_parent_via_extra'] = f"{parent_sys.name} (domain: {parent_sys.domain})"

        # Check 3: Name prefix match with assigned systems
        name_parts = sys.name.replace('.', ' ').replace('_', ' ').split()
        if len(name_parts) >= 1:
            first_word = name_parts[0]
            prefix_matches = []
            for a_sys in assigned_systems:
                a_parts = a_sys.name.replace('.', ' ').replace('_', ' ').split()
                if a_parts and a_parts[0] == first_word and a_sys.name != sys.name:
                    prefix_matches.append(f"{a_sys.name} (domain: {a_sys.domain})")
            if prefix_matches:
                evidence['prefix_matches'] = prefix_matches[:5]

        # Check 4: Is this a CompositionRelationship child of ANY parent?
        if sys.archi_id in comp_child_to_parent:
            parent_aid = comp_child_to_parent[sys.archi_id]
            parent_ac = ac_by_id.get(parent_aid)
            if parent_ac:
                evidence['composition_parent_name'] = parent_ac.name
                # Check if that parent is also unassigned
                parent_in_unassigned = any(u.archi_id == parent_aid or parent_aid in u.extra_archi_ids for u in unassigned)
                if parent_in_unassigned:
                    evidence['parent_also_unassigned'] = True

        # Check 5: Platform patterns
        name_lower = sys.name.lower()
        for p in platform_patterns:
            if p.lower() in name_lower:
                evidence['platform_pattern'] = p
                break

        # Categorize
        is_orphan = bool(evidence.get('composition_parent') or
                         evidence.get('composition_parent_via_extra') or
                         (has_dot and evidence.get('prefix_matches')) or
                         (evidence.get('composition_parent_name') and not evidence.get('parent_also_unassigned')))
        is_platform = bool(evidence.get('platform_pattern'))

        if is_platform:
            platform_cand.append((sys, evidence))
        elif is_orphan:
            orphans.append((sys, evidence))
        else:
            standalone.append((sys, evidence))

    # -- Report --
    print("\n" + "=" * 80)
    print(f"CATEGORY 1: LIKELY ORPHANED SUBSYSTEMS ({len(orphans)})")
    print("  These have evidence of a parent system in an assigned domain")
    print("=" * 80)
    for sys, evidence in sorted(orphans, key=lambda x: x[0].name):
        print(f"\n  {sys.name}")
        print(f"    c4_id: {sys.c4_id}  archi_id: {sys.archi_id[:20]}...")
        for k, v in evidence.items():
            if isinstance(v, list):
                print(f"    {k}:")
                for item in v:
                    print(f"      - {item}")
            else:
                print(f"    {k}: {v}")

    print("\n" + "=" * 80)
    print(f"CATEGORY 2: PLATFORM / INFRA CANDIDATES ({len(platform_cand)})")
    print("  Match platform patterns but weren't caught by extra_domain_patterns")
    print("=" * 80)
    for sys, evidence in sorted(platform_cand, key=lambda x: x[0].name):
        print(f"\n  {sys.name}")
        print(f"    c4_id: {sys.c4_id}")
        for k, v in evidence.items():
            if isinstance(v, list):
                print(f"    {k}:")
                for item in v:
                    print(f"      - {item}")
            else:
                print(f"    {k}: {v}")

    print("\n" + "=" * 80)
    print(f"CATEGORY 3: LIKELY STANDALONE / TRULY UNASSIGNED ({len(standalone)})")
    print("  No strong parent evidence found")
    print("=" * 80)
    for sys, evidence in sorted(standalone, key=lambda x: x[0].name):
        extra = ""
        if evidence:
            extra = "  |  " + ", ".join(f"{k}={v}" for k, v in evidence.items() if not isinstance(v, list))
        print(f"  {sys.name}{extra}")

    # -- Summary of dot-prefix groups --
    print("\n" + "=" * 80)
    print("DOT-PREFIX ANALYSIS (unassigned systems with dots)")
    print("=" * 80)
    dot_groups = defaultdict(list)
    for sys in unassigned:
        if '.' in sys.name.rstrip('.'):
            prefix = sys.name.split('.', 1)[0]
            dot_groups[prefix].append(sys.name)

    for prefix, names in sorted(dot_groups.items(), key=lambda x: -len(x[1])):
        # Check if prefix exists as an assigned system
        in_assigned = prefix in assigned_by_name
        promote_status = "PROMOTED" if prefix in config.promote_children else ""
        assigned_status = f"assigned to {assigned_by_name[prefix][1]}" if in_assigned else "NOT in assigned systems"
        print(f"\n  Prefix '{prefix}' ({len(names)} systems) — {assigned_status} {promote_status}")
        for n in sorted(names):
            print(f"    - {n}")

    # -- Composition chains from unassigned --
    print("\n" + "=" * 80)
    print("COMPOSITION RELATIONSHIPS FROM UNASSIGNED SYSTEMS")
    print("  Shows unassigned systems that are CompositionRelationship children")
    print("=" * 80)
    unassigned_with_comp = []
    for sys in unassigned:
        if sys.archi_id in comp_child_to_parent:
            parent_aid = comp_child_to_parent[sys.archi_id]
            parent_ac = ac_by_id.get(parent_aid)
            parent_name = parent_ac.name if parent_ac else f"<unknown:{parent_aid[:15]}>"
            # Find parent's domain
            parent_domain = "unknown"
            if parent_aid in assigned_by_archi:
                parent_domain = assigned_by_archi[parent_aid].domain
            else:
                # Check if parent is also unassigned
                for u in unassigned:
                    if u.archi_id == parent_aid or parent_aid in u.extra_archi_ids:
                        parent_domain = "unassigned"
                        break
            unassigned_with_comp.append((sys.name, parent_name, parent_domain))

    for child, parent, domain in sorted(unassigned_with_comp):
        marker = " *** COULD REASSIGN" if domain not in ('unassigned', 'unknown') else ""
        print(f"  {child}  -->  {parent} (domain: {domain}){marker}")

    print(f"\n  Total: {len(unassigned_with_comp)} unassigned systems with composition parents")
    reassignable = sum(1 for _, _, d in unassigned_with_comp if d not in ('unassigned', 'unknown'))
    print(f"  Reassignable (parent is assigned): {reassignable}")

    # -- Top recommendations --
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    # Group orphans by probable parent domain
    domain_gains = defaultdict(list)
    for sys, evidence in orphans:
        target_domain = None
        if 'composition_parent' in evidence:
            # Extract domain from "ParentName (domain: xxx)"
            d = evidence['composition_parent'].split('domain: ')[-1].rstrip(')')
            target_domain = d
        elif 'prefix_matches' in evidence:
            # Use first prefix match domain
            first = evidence['prefix_matches'][0]
            d = first.split('domain: ')[-1].rstrip(')')
            target_domain = d
        if target_domain:
            domain_gains[target_domain].append(sys.name)

    if domain_gains:
        print("\n  If orphans were reassigned to their parent's domain:")
        for domain, names in sorted(domain_gains.items(), key=lambda x: -len(x[1])):
            print(f"\n    {domain}: +{len(names)} systems")
            for n in sorted(names)[:10]:
                print(f"      - {n}")
            if len(names) > 10:
                print(f"      ... and {len(names) - 10} more")

    print(f"\n  Actionable: add {reassignable} systems to domain_overrides in .archi2likec4.yaml")
    print(f"  Or add their dot-prefixes to promote_children config")

    # Large unassigned dot-prefix groups that could be promoted
    print("\n  Large dot-prefix groups (candidates for promote_children):")
    for prefix, names in sorted(dot_groups.items(), key=lambda x: -len(x[1])):
        if len(names) >= 3 and prefix not in config.promote_children:
            print(f"    {prefix}: {len(names)} systems")


if __name__ == '__main__':
    main()
