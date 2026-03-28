#!/usr/bin/env python3
"""Diagnostic: analyze lost integration targets and self-loops.

Part A: Why are ~287 integration targets unresolvable?
Part B: Are ~686 self-loops truly same-system or collapsed subsystem-to-subsystem?
"""

import sys
import logging
from collections import Counter
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archi2likec4.config import load_config
from archi2likec4.pipeline import _parse, _build
from archi2likec4.builders.integrations import _build_comp_c4_path
from archi2likec4.builders.systems import _build_comp_index

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


def main():
    config = load_config(Path('.archi2likec4.yaml'))
    config.model_root = Path('architectural_repository/model').resolve()

    print("=" * 80)
    print("DIAGNOSTIC: Lost Targets & Self-Loops Analysis")
    print("=" * 80)

    # ── Phase 1: Parse ────────────────────────────────────────────────────
    parsed = _parse(config.model_root, config)
    built = _build(parsed, config)

    # Build lookup indices (same as build_integrations uses)
    comp_c4_path = _build_comp_c4_path(built.systems)
    comp_index = _build_comp_index(built.systems)

    # Build element type index from ALL parsed elements
    # archi_id -> (element_type, name)
    all_elements: dict[str, tuple[str, str]] = {}

    for ac in parsed.components:
        all_elements[ac.archi_id] = ('ApplicationComponent', ac.name)
    for fn in parsed.functions:
        all_elements[fn.archi_id] = ('ApplicationFunction', fn.name)
    for iface in parsed.interfaces:
        all_elements[iface.archi_id] = ('ApplicationInterface', iface.name)
    for do in parsed.data_objects:
        all_elements[do.archi_id] = ('DataObject', do.name)
    for te in parsed.tech_elements:
        all_elements[te.archi_id] = (te.tech_type, te.name)

    # Build iface_c4_path (same as pipeline does)
    iface_c4_path = built.iface_c4_path
    promoted_parents = built.promoted_parents

    # ══════════════════════════════════════════════════════════════════════
    # PART A: Lost targets
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("PART A: LOST (UNRESOLVABLE) INTEGRATION TARGETS")
    print("=" * 80)

    lost_rels = []  # (rel, which_side_lost: 'source'|'target'|'both')
    self_loop_rels = []  # relationships that became self-loops

    for rel in parsed.relationships:
        if rel.rel_type == 'AccessRelationship':
            continue
        if rel.rel_type in ('CompositionRelationship', 'AggregationRelationship',
                            'RealizationRelationship', 'AssignmentRelationship'):
            continue
        if rel.source_type == 'ApplicationFunction' or rel.target_type == 'ApplicationFunction':
            continue

        # Resolve source
        src_paths = []
        if rel.source_type == 'ApplicationComponent':
            path = comp_c4_path.get(rel.source_id)
            if path:
                src_paths = [path]
            elif promoted_parents and rel.source_id in promoted_parents:
                src_paths = list(promoted_parents[rel.source_id])
        elif rel.source_type == 'ApplicationInterface':
            path = iface_c4_path.get(rel.source_id)
            if path:
                src_paths = [path]

        # Resolve target
        tgt_paths = []
        if rel.target_type == 'ApplicationComponent':
            path = comp_c4_path.get(rel.target_id)
            if path:
                tgt_paths = [path]
            elif promoted_parents and rel.target_id in promoted_parents:
                tgt_paths = list(promoted_parents[rel.target_id])
        elif rel.target_type == 'ApplicationInterface':
            path = iface_c4_path.get(rel.target_id)
            if path:
                tgt_paths = [path]

        if not src_paths or not tgt_paths:
            src_lost = not src_paths
            tgt_lost = not tgt_paths
            side = 'both' if src_lost and tgt_lost else ('source' if src_lost else 'target')
            lost_rels.append((rel, side))
            continue

        # Check for self-loops
        for sp in src_paths:
            sp_sys = sp.split('.')[0]
            for tp in tgt_paths:
                tp_sys = tp.split('.')[0]
                if sp_sys == tp_sys:
                    self_loop_rels.append((rel, sp, tp))

    print(f"\nTotal eligible relationships: {built.diagnostics.intg_total_eligible}")
    print(f"Lost (unresolvable): {len(lost_rels)}")
    print(f"Self-loops detected: {len(self_loop_rels)}")

    # ── Breakdown by which side is lost ──────────────────────────────────
    side_counts = Counter(side for _, side in lost_rels)
    print(f"\nLost side breakdown:")
    for side, count in side_counts.most_common():
        print(f"  {side}: {count}")

    # ── Breakdown by WHY the endpoint is lost ────────────────────────────
    reason_counter = Counter()
    lost_details = []  # (rel, side, src_reason, tgt_reason)

    for rel, side in lost_rels:
        reasons = {}
        for endpoint, eid, etype in [('source', rel.source_id, rel.source_type),
                                      ('target', rel.target_id, rel.target_type)]:
            if endpoint == 'source' and side == 'target':
                reasons[endpoint] = 'resolved'
                continue
            if endpoint == 'target' and side == 'source':
                reasons[endpoint] = 'resolved'
                continue

            if etype == 'ApplicationComponent':
                if eid in all_elements:
                    elem_type, elem_name = all_elements[eid]
                    # It's a known component but not in comp_c4_path
                    if eid in comp_c4_path:
                        reasons[endpoint] = 'resolved (unexpected)'
                    else:
                        # Check if it's in promoted parents
                        if promoted_parents and eid in promoted_parents:
                            reasons[endpoint] = 'promoted_parent'
                        else:
                            reasons[endpoint] = f'AppComponent_not_in_systems ({elem_name})'
                else:
                    reasons[endpoint] = 'missing_from_parsed_elements'
            elif etype == 'ApplicationInterface':
                if eid in iface_c4_path:
                    reasons[endpoint] = 'resolved (unexpected)'
                elif eid in all_elements:
                    reasons[endpoint] = f'unresolved_interface ({all_elements[eid][1]})'
                else:
                    reasons[endpoint] = 'interface_missing_from_parsed'
            elif etype == 'DataObject':
                reasons[endpoint] = 'DataObject (filtered by type)'
            elif etype == 'ApplicationFunction':
                reasons[endpoint] = 'AppFunction (filtered by type)'
            else:
                if eid in all_elements:
                    reasons[endpoint] = f'tech_element ({all_elements[eid][0]}: {all_elements[eid][1]})'
                else:
                    reasons[endpoint] = f'unknown_type ({etype})'

        lost_details.append((rel, side, reasons.get('source', '?'), reasons.get('target', '?')))

    # Count reasons
    src_reasons = Counter()
    tgt_reasons = Counter()
    for rel, side, src_r, tgt_r in lost_details:
        if side in ('source', 'both'):
            # Simplify reason for counting
            simplified = src_r.split(' (')[0] if '(' in src_r else src_r
            src_reasons[simplified] += 1
        if side in ('target', 'both'):
            simplified = tgt_r.split(' (')[0] if '(' in tgt_r else tgt_r
            tgt_reasons[simplified] += 1

    print(f"\nSource-side loss reasons:")
    for reason, count in src_reasons.most_common():
        print(f"  {reason}: {count}")

    print(f"\nTarget-side loss reasons:")
    for reason, count in tgt_reasons.most_common():
        print(f"  {reason}: {count}")

    # ── Categorize unresolved AppComponents ──────────────────────────────
    parsed_ac_ids = {ac.archi_id for ac in parsed.components}
    indexed_ids = set(comp_c4_path.keys())
    in_parsed_not_indexed = parsed_ac_ids - indexed_ids
    promoted_ids = set(promoted_parents.keys()) if promoted_parents else set()
    truly_missing = in_parsed_not_indexed - promoted_ids

    print(f"\n--- AppComponent resolution gap ---")
    print(f"  Parsed AppComponents: {len(parsed_ac_ids)}")
    print(f"  Indexed in comp_c4_path: {len(indexed_ids)}")
    print(f"  In parsed but NOT indexed: {len(in_parsed_not_indexed)}")
    print(f"  Of those, promoted parents: {len(in_parsed_not_indexed & promoted_ids)}")
    print(f"  Truly missing (not indexed, not promoted): {len(truly_missing)}")

    # What are these missing AppComponents?
    if truly_missing:
        missing_names = []
        for ac in parsed.components:
            if ac.archi_id in truly_missing:
                missing_names.append(ac.name)
        print(f"\n  Missing AppComponents (not in any system, first 20):")
        for name in sorted(missing_names)[:20]:
            print(f"    - {name}")

    # ── Lost targets involving non-AppComponent types ────────────────────
    lost_by_endpoint_type = Counter()
    for rel, side in lost_rels:
        if side in ('source', 'both'):
            lost_by_endpoint_type[f'src:{rel.source_type}'] += 1
        if side in ('target', 'both'):
            lost_by_endpoint_type[f'tgt:{rel.target_type}'] += 1

    print(f"\nEndpoint types involved in lost relationships:")
    for key, count in lost_by_endpoint_type.most_common():
        print(f"  {key}: {count}")

    # ── Top-10 examples of lost targets ──────────────────────────────────
    print(f"\nTop-10 examples of lost relationships:")
    print(f"{'#':>3} {'Side':>6} {'Rel Type':<28} {'Source Type':<22} {'Source Name':<35} {'Target Type':<22} {'Target Name':<35}")
    print("-" * 155)

    shown = 0
    for rel, side, src_r, tgt_r in lost_details[:30]:
        if shown >= 10:
            break
        src_name = all_elements.get(rel.source_id, ('?', f'[{rel.source_id[:12]}...]'))[1]
        tgt_name = all_elements.get(rel.target_id, ('?', f'[{rel.target_id[:12]}...]'))[1]
        src_type = all_elements.get(rel.source_id, (rel.source_type, ''))[0]
        tgt_type = all_elements.get(rel.target_id, (rel.target_type, ''))[0]
        print(f"{shown+1:>3} {side:>6} {rel.rel_type:<28} {src_type:<22} {src_name[:34]:<35} {tgt_type:<22} {tgt_name[:34]:<35}")
        shown += 1

    # ── Deeper: what rel types have unresolvable ApplicationInterfaces? ──
    unresolved_iface_rels = [(r, s) for r, s in lost_rels
                             if (s in ('source', 'both') and r.source_type == 'ApplicationInterface')
                             or (s in ('target', 'both') and r.target_type == 'ApplicationInterface')]
    if unresolved_iface_rels:
        print(f"\nUnresolved ApplicationInterface relationships: {len(unresolved_iface_rels)}")
        iface_rel_types = Counter(r.rel_type for r, _ in unresolved_iface_rels)
        for rt, c in iface_rel_types.most_common():
            print(f"  {rt}: {c}")

    # ══════════════════════════════════════════════════════════════════════
    # PART B: Self-loops
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("PART B: SELF-LOOP ANALYSIS")
    print("=" * 80)

    print(f"\nTotal self-loop relationships (before dedup): {len(self_loop_rels)}")

    # Classify: truly same element, or subsystem-to-subsystem within same parent?
    truly_same = 0
    sub_to_sub = 0
    sys_to_sub = 0  # system-level to its own subsystem

    classification_details = []

    for rel, sp, tp in self_loop_rels:
        sp_parts = sp.split('.')
        tp_parts = tp.split('.')

        if sp == tp:
            truly_same += 1
            classification_details.append((rel, sp, tp, 'same_element'))
        elif len(sp_parts) >= 2 and len(tp_parts) >= 2 and sp_parts[0] == tp_parts[0]:
            sub_to_sub += 1
            classification_details.append((rel, sp, tp, 'subsystem_to_subsystem'))
        elif len(sp_parts) == 1 or len(tp_parts) == 1:
            sys_to_sub += 1
            classification_details.append((rel, sp, tp, 'system_to_own_subsystem'))
        else:
            truly_same += 1
            classification_details.append((rel, sp, tp, 'other_same_system'))

    print(f"\nSelf-loop classification:")
    print(f"  Same element (X -> X):          {truly_same}")
    print(f"  Subsystem-to-subsystem (A.x -> A.y): {sub_to_sub}")
    print(f"  System-to-own-subsystem:        {sys_to_sub}")

    # ── Top-10 systems with most self-loops ──────────────────────────────
    sys_loop_count = Counter()
    for rel, sp, tp in self_loop_rels:
        sys_id = sp.split('.')[0]
        sys_loop_count[sys_id] += 1

    # Map c4_id to name
    c4_to_name = {s.c4_id: s.name for s in built.systems}

    print(f"\nTop-10 systems with most self-loops:")
    print(f"{'#':>3} {'c4_id':<35} {'System Name':<40} {'Count':>6}")
    print("-" * 90)
    for i, (sys_id, count) in enumerate(sys_loop_count.most_common(10)):
        name = c4_to_name.get(sys_id, '?')
        print(f"{i+1:>3} {sys_id:<35} {name:<40} {count:>6}")

    # ── Examples: show original source/target names before resolution ────
    print(f"\nSelf-loop examples (what ArchiMate elements collapsed to same system):")
    print(f"{'#':>3} {'System':<30} {'Type':<25} {'Src Path':<35} {'Tgt Path':<35} {'Src Element':<35} {'Tgt Element':<35}")
    print("-" * 200)

    shown = 0
    seen_systems = set()
    for rel, sp, tp, classification in classification_details:
        if shown >= 15:
            break
        sys_id = sp.split('.')[0]
        sys_name = c4_to_name.get(sys_id, '?')

        src_name = all_elements.get(rel.source_id, ('?', f'[{rel.source_id[:12]}...]'))[1]
        tgt_name = all_elements.get(rel.target_id, ('?', f'[{rel.target_id[:12]}...]'))[1]

        print(f"{shown+1:>3} {sys_name[:29]:<30} {classification:<25} {sp[:34]:<35} {tp[:34]:<35} {src_name[:34]:<35} {tgt_name[:34]:<35}")
        shown += 1
        seen_systems.add(sys_id)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"""
Eligible relationships:   {built.diagnostics.intg_total_eligible}
Lost (unresolvable):      {len(lost_rels)}  ({(len(lost_rels)*100/built.diagnostics.intg_total_eligible if built.diagnostics.intg_total_eligible else 0.0):.1f}%)
Self-loops (filtered):    {len(self_loop_rels)}
Successful integrations:  {len(built.integrations)} (deduplicated)

Lost breakdown:
  - Source lost:  {side_counts.get('source', 0)}
  - Target lost:  {side_counts.get('target', 0)}
  - Both lost:    {side_counts.get('both', 0)}

Self-loop breakdown:
  - Truly same element:       {truly_same}
  - Subsystem-to-subsystem:   {sub_to_sub}
  - System-to-own-subsystem:  {sys_to_sub}
""")


if __name__ == '__main__':
    main()
