#!/usr/bin/env python3
"""Diagnostic: understand WHERE 1663 duplicate integrations come from.

Runs the parse+build pipeline, then replays the build_integrations logic
to capture raw (pre-dedup) integration pairs and show duplication patterns.
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

from archi2likec4.config import load_config
from archi2likec4.pipeline import _parse, _build
from archi2likec4.builders.integrations import _build_comp_c4_path

config = load_config(None)
config.model_root = Path('architectural_repository/model').resolve()
if not config.model_root.is_dir():
    print(f'ERROR: model root not found: {config.model_root}', file=sys.stderr)
    sys.exit(2)

print(f'Model root: {config.model_root}')
print('Running parse + build pipeline...')
parsed = _parse(config.model_root, config)
built = _build(parsed, config)

systems = built.systems
comp_c4_path, _ = _build_comp_c4_path(systems)
iface_c4_path = built.iface_c4_path
promoted_parents = built.promoted_parents

# ── Replay build_integrations logic, but keep ALL raw pairs ──────────────

raw_pairs = []  # list of (src_sys, tgt_sys, label, rel_type, src_type, tgt_type)

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
        continue

    name = rel.name.strip() if rel.name else ''

    for sp in src_paths:
        sp_sys = sp.split('.')[0]
        for tp in tgt_paths:
            tp_sys = tp.split('.')[0]
            if sp_sys == tp_sys:
                continue
            raw_pairs.append((sp_sys, tp_sys, name, rel.rel_type,
                              rel.source_type, rel.target_type))

# ── Group by (src_sys, tgt_sys) ──────────────────────────────────────────

grouped = defaultdict(list)
for src, tgt, label, rtype, stype, ttype in raw_pairs:
    grouped[(src, tgt)].append((label, rtype, stype, ttype))

# Build c4_id -> name map
c4_to_name = {s.c4_id: s.name for s in systems}

# ── Summary ──────────────────────────────────────────────────────────────

print()
print('=' * 80)
print('  DUPLICATE INTEGRATION DIAGNOSTICS')
print('=' * 80)

print(f'\n  Total raw cross-system pairs (before dedup): {len(raw_pairs)}')
print(f'  Unique (src_sys, tgt_sys) pairs:             {len(grouped)}')
print(f'  Final integrations (after dedup):            {len(built.integrations)}')
print(f'  Duplicates removed:                          {len(raw_pairs) - len(grouped)}')

# ── Occurrence distribution ──────────────────────────────────────────────

print('\n' + '-' * 80)
print('  OCCURRENCE DISTRIBUTION')
print('  (how many system pairs have N raw relationships)')
print('-' * 80)

occurrence_counts = Counter(len(v) for v in grouped.values())
brackets = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 9), (10, 19), (20, 49), (50, 99), (100, 999)]

for lo, hi in brackets:
    count = sum(c for occ, c in occurrence_counts.items() if lo <= occ <= hi)
    if count > 0:
        if lo == hi:
            print(f'    {lo:>4} occurrence(s):  {count:>4} pairs')
        else:
            print(f'    {lo:>3}-{hi:<3} occurrences: {count:>4} pairs')

# Total duplicate relationships contributed
total_dupes = sum(len(v) - 1 for v in grouped.values() if len(v) > 1)
pairs_with_dupes = sum(1 for v in grouped.values() if len(v) > 1)
print(f'\n    Pairs with duplicates: {pairs_with_dupes}')
print(f'    Total excess relationships (duplicates): {total_dupes}')

# ── Top-10 most duplicated pairs ─────────────────────────────────────────

print('\n' + '-' * 80)
print('  TOP-10 MOST DUPLICATED PAIRS')
print('-' * 80)

top_pairs = sorted(grouped.items(), key=lambda x: -len(x[1]))[:10]

for rank, ((src, tgt), entries) in enumerate(top_pairs, 1):
    src_name = c4_to_name.get(src, src)
    tgt_name = c4_to_name.get(tgt, tgt)
    print(f'\n  #{rank}  {src_name} -> {tgt_name}  ({len(entries)} raw relationships)')

    # Count by rel_type
    rtype_counter = Counter(rtype for _, rtype, _, _ in entries)
    print(f'       Rel types: {dict(rtype_counter)}')

    # Count by source/target type combo
    endpoint_counter = Counter((stype, ttype) for _, _, stype, ttype in entries)
    print(f'       Endpoint types: {dict(endpoint_counter)}')

    # Show unique labels
    labels = [label for label, _, _, _ in entries if label]
    unique_labels = list(dict.fromkeys(labels))
    empty_count = sum(1 for label, _, _, _ in entries if not label)
    if unique_labels:
        shown = unique_labels[:8]
        print(f'       Labels ({len(unique_labels)} unique, {empty_count} empty):')
        for lbl in shown:
            count = labels.count(lbl)
            suffix = f' (x{count})' if count > 1 else ''
            print(f'         - "{lbl}"{suffix}')
        if len(unique_labels) > 8:
            print(f'         ... and {len(unique_labels) - 8} more')
    else:
        print(f'       Labels: all {len(entries)} have empty label')

# ── Fan-out analysis: how much duplication comes from promoted parents? ──

print('\n' + '-' * 80)
print('  FAN-OUT ANALYSIS (promoted parents)')
print('-' * 80)

fanout_pairs = 0
fanout_raw = 0
non_fanout_pairs = 0
non_fanout_raw = 0

for (src, tgt), entries in grouped.items():
    if len(entries) > 1:
        fanout_pairs += 1
        fanout_raw += len(entries)
    else:
        non_fanout_pairs += 1
        non_fanout_raw += len(entries)

# Count how many raw pairs involved fan-out (promoted parent source or target)
promoted_ids = set(promoted_parents.keys()) if promoted_parents else set()
fanout_count = 0
for rel in parsed.relationships:
    if rel.source_id in promoted_ids or rel.target_id in promoted_ids:
        fanout_count += 1
print(f'  Relationships referencing promoted parents: {fanout_count}')
print(f'  Promoted parent archi_ids: {len(promoted_ids)}')

# ── Relationship type breakdown for duplicated pairs ─────────────────────

print('\n' + '-' * 80)
print('  REL TYPE BREAKDOWN (for pairs with 2+ raw relationships)')
print('-' * 80)

all_dup_rtypes = Counter()
for (src, tgt), entries in grouped.items():
    if len(entries) > 1:
        for _, rtype, _, _ in entries:
            all_dup_rtypes[rtype] += 1

for rtype, count in all_dup_rtypes.most_common():
    print(f'    {rtype:<35} {count}')

# ── Endpoint type breakdown for duplicated pairs ─────────────────────────

print('\n' + '-' * 80)
print('  ENDPOINT TYPE BREAKDOWN (for pairs with 2+ raw relationships)')
print('-' * 80)

all_dup_endpoints = Counter()
for (src, tgt), entries in grouped.items():
    if len(entries) > 1:
        for _, _, stype, ttype in entries:
            all_dup_endpoints[(stype, ttype)] += 1

for (stype, ttype), count in all_dup_endpoints.most_common():
    print(f'    {stype} -> {ttype}: {count}')

print('\n' + '=' * 80)
print('  Done.')
print('=' * 80)
