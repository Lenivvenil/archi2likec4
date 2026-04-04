"""Gap data model and penalty table."""

from __future__ import annotations

from dataclasses import dataclass, field


class GapCode:
    """Gap code constants."""

    DEPLOY = 'GAP-DEPLOY'
    ZONE = 'GAP-ZONE'
    DOMAIN = 'GAP-DOMAIN'
    INTEG = 'GAP-INTEG'
    SHALLOW = 'GAP-SHALLOW'
    ORPHAN = 'GAP-ORPHAN'
    DUP = 'GAP-DUP'
    DESC = 'GAP-DESC'
    REF = 'GAP-REF'
    ENV = 'GAP-ENV'


class Severity:
    """Severity level constants."""

    BLOCKER = 'blocker'
    DEGRADED = 'degraded'
    COSMETIC = 'cosmetic'


@dataclass(frozen=True)
class Gap:
    """A detected gap in the architecture model."""

    code: str
    severity: str
    element_id: str
    element_name: str
    context: dict[str, str] = field(default_factory=dict)
    remediation: str = ''


# Penalty per gap code (subtracted from 100)
PENALTY_TABLE: dict[str, int] = {
    GapCode.DEPLOY: 30,
    GapCode.ZONE: 25,
    GapCode.DUP: 20,
    GapCode.REF: 20,
    GapCode.INTEG: 15,
    GapCode.DOMAIN: 10,
    GapCode.SHALLOW: 10,
    GapCode.ENV: 10,
    GapCode.DESC: 5,
    GapCode.ORPHAN: 3,
}

# All known gap codes in severity order
ALL_GAP_CODES: list[str] = [
    GapCode.DEPLOY, GapCode.ZONE, GapCode.DUP, GapCode.REF,
    GapCode.INTEG, GapCode.DOMAIN, GapCode.SHALLOW, GapCode.ENV,
    GapCode.DESC, GapCode.ORPHAN,
]
