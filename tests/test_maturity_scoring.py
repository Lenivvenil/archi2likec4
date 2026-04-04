"""Tests for maturity scoring engine."""

from archi2likec4.maturity.gaps import Gap, GapCode, Severity
from archi2likec4.maturity.scoring import (
    compute_repo_score,
    compute_system_score,
    score_to_tier,
    tier_emoji,
)
from archi2likec4.models import System
from tests.helpers import MockBuilt


def _sys(c4_id: str, name: str = '') -> System:
    return System(c4_id=c4_id, name=name or c4_id, archi_id=f'a-{c4_id}')


def _gap(code: str, element_id: str = 's1', severity: str = Severity.BLOCKER) -> Gap:
    return Gap(code=code, severity=severity, element_id=element_id, element_name=element_id)


class TestScoreToTier:
    def test_complete(self):
        assert score_to_tier(100) == 'complete'
        assert score_to_tier(90) == 'complete'

    def test_partial(self):
        assert score_to_tier(89) == 'partial'
        assert score_to_tier(70) == 'partial'

    def test_skeletal(self):
        assert score_to_tier(69) == 'skeletal'
        assert score_to_tier(40) == 'skeletal'

    def test_stub(self):
        assert score_to_tier(39) == 'stub'
        assert score_to_tier(0) == 'stub'


class TestTierEmoji:
    def test_all_tiers(self):
        assert tier_emoji('complete') == '\U0001f7e2'
        assert tier_emoji('partial') == '\U0001f7e1'
        assert tier_emoji('skeletal') == '\U0001f7e0'
        assert tier_emoji('stub') == '\U0001f534'
        assert tier_emoji('unknown') == '\u2753'


class TestComputeSystemScore:
    def test_perfect_score_no_gaps(self):
        score = compute_system_score('s1', 'Sys1', [])
        assert score.score == 100
        assert score.tier == 'complete'

    def test_deploy_gap_penalty(self):
        gaps = [_gap(GapCode.DEPLOY)]
        score = compute_system_score('s1', 'Sys1', gaps)
        assert score.score == 70  # 100 - 30
        assert score.tier == 'partial'

    def test_multiple_gaps_stack(self):
        gaps = [_gap(GapCode.DEPLOY), _gap(GapCode.INTEG, severity=Severity.DEGRADED)]
        score = compute_system_score('s1', 'Sys1', gaps)
        assert score.score == 55  # 100 - 30 - 15
        assert score.tier == 'skeletal'

    def test_score_floors_at_zero(self):
        gaps = [
            _gap(GapCode.DEPLOY), _gap(GapCode.ZONE),
            _gap(GapCode.DUP), _gap(GapCode.REF),
        ]
        score = compute_system_score('s1', 'Sys1', gaps)
        assert score.score == 5  # 100 - 30 - 25 - 20 - 20 = 5
        assert score.tier == 'stub'


class TestComputeRepoScore:
    def test_empty_repo(self):
        built = MockBuilt(systems=[])
        score = compute_repo_score(built, [])
        assert score.score == 100
        assert score.tier == 'complete'
        assert score.total_gaps == 0

    def test_single_system_with_gaps(self):
        built = MockBuilt(systems=[_sys('s1')])
        gaps = [_gap(GapCode.DOMAIN, severity=Severity.DEGRADED)]
        score = compute_repo_score(built, gaps)
        assert score.score == 90  # 100 - 10
        assert score.total_gaps == 1
        assert len(score.system_scores) == 1

    def test_blocker_count(self):
        built = MockBuilt(systems=[_sys('s1')])
        gaps = [
            _gap(GapCode.DEPLOY, severity=Severity.BLOCKER),
            _gap(GapCode.DESC, severity=Severity.COSMETIC),
        ]
        score = compute_repo_score(built, gaps)
        assert score.blocker_count == 1

    def test_system_scores_sorted_by_score(self):
        s1, s2 = _sys('s1'), _sys('s2')
        built = MockBuilt(systems=[s1, s2])
        gaps = [_gap(GapCode.DEPLOY, element_id='s1')]
        score = compute_repo_score(built, gaps)
        assert score.system_scores[0].system_id == 's1'  # lower score first
        assert score.system_scores[0].score < score.system_scores[1].score
