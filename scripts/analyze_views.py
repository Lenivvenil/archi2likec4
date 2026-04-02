#!/usr/bin/env python3
"""Analyze LikeC4 exported JSON model — deployment view node counts and types.

Usage:
    likec4 export json -o /tmp/likec4-model.json
    python scripts/analyze_views.py /tmp/likec4-model.json [view_filter]

Examples:
    python scripts/analyze_views.py /tmp/likec4-model.json deployment_aim_prod
    python scripts/analyze_views.py /tmp/likec4-model.json deploy  # all deployment views
"""

import json
import sys
from collections import Counter
from pathlib import Path


def analyze_view(view_id: str, view: dict) -> None:
    nodes = view.get('nodes', [])
    edges = view.get('edges', [])
    kind_counter: Counter[str] = Counter()
    for n in nodes:
        kind_counter[n.get('kind', 'unknown')] += 1

    print(f"\n{'=' * 60}")
    print(f"View: {view_id}")
    print(f"  Total nodes: {len(nodes)}, edges: {len(edges)}")
    print(f"  By kind:")
    for kind, count in kind_counter.most_common():
        print(f"    {kind}: {count}")
    print(f"  First 20 nodes:")
    for n in nodes[:20]:
        title = n.get('title', n.get('id', '?'))
        kind = n.get('kind', '?')
        depth = n.get('depth', '?')
        print(f"    [{kind}] {title}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    json_path = Path(sys.argv[1])
    view_filter = sys.argv[2] if len(sys.argv) > 2 else ''

    with open(json_path) as f:
        data = json.load(f)

    views = data.get('views', {})
    matched = {vid: v for vid, v in views.items() if view_filter in vid}

    if not matched:
        print(f"No views matching '{view_filter}'. Available deployment views:")
        for vid in sorted(views):
            if 'deploy' in vid.lower():
                print(f"  {vid}")
        sys.exit(1)

    for vid, v in sorted(matched.items()):
        analyze_view(vid, v)


if __name__ == '__main__':
    main()
