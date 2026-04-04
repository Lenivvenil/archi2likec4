"""Tests for maturity reporters (MATURITY.md + JSON)."""

import json

from archi2likec4.maturity.gaps import Gap, GapCode, Severity
from archi2likec4.maturity.reporters import generate_maturity_json, generate_maturity_md
from archi2likec4.maturity.scoring import RepoScore, SystemScore
from tests.helpers import MockConfig


def _score(system_id: str, score: int, tier: str, gaps: list[Gap] | None = None) -> SystemScore:
    return SystemScore(
        system_id=system_id,
        system_name=system_id.upper(),
        score=score,
        tier=tier,
        gaps=gaps or [],
    )


class TestGenerateMaturityMd:
    def test_contains_header_ru(self):
        repo = RepoScore(score=75, tier='partial', system_scores=[], total_gaps=5, blocker_count=2)
        md = generate_maturity_md(repo, MockConfig(language='ru'))
        assert 'Отчёт зрелости' in md
        assert '75/100' in md
        assert 'PARTIAL' in md

    def test_contains_header_en(self):
        repo = RepoScore(score=95, tier='complete', system_scores=[], total_gaps=0, blocker_count=0)
        md = generate_maturity_md(repo, MockConfig(language='en'))
        assert 'Architecture Model Maturity Report' in md
        assert '95/100' in md

    def test_tier_distribution(self):
        scores = [
            _score('s1', 100, 'complete'),
            _score('s2', 50, 'skeletal'),
        ]
        repo = RepoScore(score=75, tier='partial', system_scores=scores, total_gaps=1, blocker_count=0)
        md = generate_maturity_md(repo, MockConfig())
        assert 'complete' in md
        assert 'skeletal' in md

    def test_gap_distribution(self):
        gap = Gap(code=GapCode.DEPLOY, severity=Severity.BLOCKER, element_id='s1', element_name='S1')
        scores = [_score('s1', 70, 'partial', [gap])]
        repo = RepoScore(score=70, tier='partial', system_scores=scores, total_gaps=1, blocker_count=1)
        md = generate_maturity_md(repo, MockConfig())
        assert 'GAP-DEPLOY' in md

    def test_worst_best_tables(self):
        scores = [_score('bad', 20, 'stub'), _score('good', 100, 'complete')]
        repo = RepoScore(score=60, tier='skeletal', system_scores=scores, total_gaps=1, blocker_count=0)
        md = generate_maturity_md(repo, MockConfig(language='en'))
        assert 'Worst 10' in md
        assert 'Best 10' in md
        assert 'BAD' in md
        assert 'GOOD' in md


class TestGenerateMaturityJson:
    def test_valid_json(self):
        repo = RepoScore(score=80, tier='partial', system_scores=[], total_gaps=3, blocker_count=1)
        raw = generate_maturity_json(repo)
        data = json.loads(raw)
        assert data['score'] == 80
        assert data['tier'] == 'partial'
        assert data['total_gaps'] == 3
        assert data['blocker_count'] == 1

    def test_includes_systems(self):
        gap = Gap(code=GapCode.DESC, severity=Severity.COSMETIC, element_id='s1', element_name='S1')
        scores = [_score('s1', 95, 'complete', [gap])]
        repo = RepoScore(score=95, tier='complete', system_scores=scores, total_gaps=1, blocker_count=0)
        data = json.loads(generate_maturity_json(repo))
        assert len(data['systems']) == 1
        assert data['systems'][0]['id'] == 's1'
        assert len(data['systems'][0]['gaps']) == 1
        assert data['systems'][0]['gaps'][0]['code'] == 'GAP-DESC'
