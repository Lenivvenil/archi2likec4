"""Maturity auditor: GAP detection, scoring, and reporting."""

from .detectors import detect_all_gaps
from .gaps import Gap, GapCode, Severity
from .reporters import generate_maturity_json, generate_maturity_md
from .scaffold import generate_scaffold_deployment
from .scoring import RepoScore, SystemScore, compute_repo_score

__all__ = [
    'Gap',
    'GapCode',
    'RepoScore',
    'Severity',
    'SystemScore',
    'compute_repo_score',
    'detect_all_gaps',
    'generate_maturity_json',
    'generate_maturity_md',
    'generate_scaffold_deployment',
]
