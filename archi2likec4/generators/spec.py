"""Generate LikeC4 specification block."""

from __future__ import annotations


def generate_spec() -> str:
    return """\
specification {

  // ── Colors ──────────────────────────────────────────────
  color archi-app #7EB8DA
  color archi-app-light #BDE0F0
  color archi-data #F0D68A
  color archi-store #B0B0B0

  // ── Business domains ──────────────────────────────────
  element domain {
    style {
      shape rectangle
      color amber
    }
  }

  element subdomain {
    style {
      shape rectangle
      color secondary
    }
  }

  // ── Application landscape ──────────────────────────────
  element system {
    style {
      shape component
      color archi-app
    }
  }

  element subsystem {
    style {
      shape component
      color archi-app-light
    }
  }

  element appFunction {
    style {
      shape rectangle
      color archi-app-light
    }
  }

  // ── Data layer ─────────────────────────────────────────
  element dataEntity {
    style {
      shape document
      color archi-data
    }
  }

  element dataStore {
    style {
      shape cylinder
      color archi-store
    }
  }

  // ── Infrastructure / Deployment ──────────────────────
  color archi-tech #93D275
  color archi-tech-light #C5E6B8

  element infraNode {
    style {
      shape rectangle
      color archi-tech
    }
  }

  element infraSoftware {
    style {
      shape cylinder
      color archi-tech-light
    }
  }

  element infraZone {
    style {
      shape rectangle
      color archi-tech
      border dotted
    }
  }

  element infraLocation {
    style {
      shape rectangle
      color archi-tech
      border dashed
    }
  }

  // ── Relationship kinds ─────────────────────────────────
  relationship persists {
    color archi-store
    line dashed
  }

  relationship deployedOn {
    color archi-tech
    line dashed
  }

  // ── Tags ───────────────────────────────────────────────
  tag to_review
  tag external
  tag entity
  tag store
  tag infrastructure
  tag cluster
  tag device
  tag network
}
"""
