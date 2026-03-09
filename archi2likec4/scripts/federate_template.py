#!/usr/bin/env python3
"""
Federate architecture: pull system specs from project repositories.

Pulls system.c4 and system.yaml from registered project repos
into the systems/ directory for the central LikeC4 build.

Usage:
    python scripts/federate.py                  # pull all
    python scripts/federate.py --repo payment   # pull matching repos only

Registry: scripts/federation-registry.yaml
"""

import argparse
import os
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml")
    sys.exit(1)

REGISTRY_PATH = "scripts/federation-registry.yaml"
SYSTEMS_DIR = "systems"
CLONE_DIR = ".federation-cache"
FEDERATION_MARKERS = ("// Federated from:", "# Federated from:")


def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        print(f"Registry not found: {REGISTRY_PATH}")
        sys.exit(1)
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clone_or_pull(repo_url, local_path, branch="main", sha=""):
    if os.path.exists(local_path):
        print(f"  Pulling {local_path} (branch: {branch})...")
        # Ensure correct branch before pulling
        subprocess.run(
            ["git", "-C", local_path, "fetch", "--quiet", "origin", branch],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", local_path, "checkout", branch, "--quiet"],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run(
            ["git", "-C", local_path, "pull", "--quiet", "origin", branch],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"git pull failed (exit {result.returncode}): {stderr}")
    else:
        print(f"  Cloning {repo_url}...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch,
             "--quiet", repo_url, local_path],
            check=True, capture_output=True,
        )
    # Pin to specific SHA if provided (overrides branch HEAD)
    if sha:
        print(f"  Checking out SHA {sha[:12]}...")
        # Fetch full history for the SHA (shallow clones may not have it)
        subprocess.run(
            ["git", "-C", local_path, "fetch", "--quiet", "origin", sha],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", local_path, "checkout", sha, "--quiet"],
            check=True, capture_output=True, text=True,
        )


def _is_safe_relpath(p):
    """Reject paths with traversal or absolute components."""
    if not p or os.path.isabs(p):
        return False
    # Check both Unix and Windows separators for cross-platform safety
    parts = p.replace("\\", "/").split("/")
    return ".." not in parts


def federate(filter_name=None):
    registry = load_registry()
    if not isinstance(registry, dict):
        print(f"ERROR: Registry must be a YAML mapping, got {type(registry).__name__}")
        sys.exit(1)
    os.makedirs(SYSTEMS_DIR, exist_ok=True)
    os.makedirs(CLONE_DIR, exist_ok=True)

    projects = registry.get("projects", [])
    if not projects:
        print("No projects in registry")
        return

    success = 0
    errors = 0

    for project in projects:
        if not isinstance(project, dict):
            print(f"  ERROR: Invalid project entry (expected mapping): {project!r}")
            errors += 1
            continue
        name = project.get("name")
        repo = project.get("repo")
        if not name or not repo:
            print(f"  ERROR: Project missing required 'name' or 'repo': {project!r}")
            errors += 1
            continue
        if "/" in name or "\\" in name or ".." in name:
            print(f"  ERROR: Invalid project name: {name!r}")
            errors += 1
            continue
        branch = project.get("branch", "main")
        sha = project.get("sha", "")
        c4_path = project.get("c4_path", "docs/system.c4")
        yaml_path = project.get("yaml_path", "docs/system.yaml")

        if not _is_safe_relpath(c4_path) or not _is_safe_relpath(yaml_path):
            print(f"  ERROR: Invalid path in registry for {name!r}: c4={c4_path!r} yaml={yaml_path!r}")
            errors += 1
            continue

        if filter_name and filter_name not in name:
            continue

        print(f"\n[{name}]")
        local_path = os.path.join(CLONE_DIR, name)

        try:
            clone_or_pull(repo, local_path, branch, sha)

            # Copy system.c4
            src_c4 = os.path.join(local_path, c4_path)
            if os.path.exists(src_c4):
                dst_c4 = os.path.join(SYSTEMS_DIR, f"{name}.c4")
                with open(src_c4, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(dst_c4, "w", encoding="utf-8") as f:
                    f.write(f"// Federated from: {repo}\n")
                    f.write(f"// Source: {c4_path} (branch: {branch})")
                    if sha:
                        f.write(f" @ {sha[:12]}")
                    f.write("\n")
                    f.write(f"// Auto-synced by scripts/federate.py\n\n")
                    f.write(content)
                print(f"  OK {c4_path} -> {dst_c4}")
            else:
                print(f"  WARN {c4_path} not found in repo")
                errors += 1
                continue

            # Copy system.yaml
            src_yaml = os.path.join(local_path, yaml_path)
            if os.path.exists(src_yaml):
                dst_yaml = os.path.join(SYSTEMS_DIR, f"{name}.yaml")
                with open(src_yaml, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(dst_yaml, "w", encoding="utf-8") as f:
                    f.write(f"# Federated from: {repo}\n")
                    f.write(f"# Source: {yaml_path} (branch: {branch})")
                    if sha:
                        f.write(f" @ {sha[:12]}")
                    f.write("\n")
                    f.write(f"# Auto-synced by scripts/federate.py\n\n")
                    f.write(content)
                print(f"  OK {yaml_path} -> {dst_yaml}")
            else:
                print(f"  WARN {yaml_path} not found (optional)")

            success += 1

        except subprocess.CalledProcessError as e:
            print(f"  ERROR Git: {e}")
            errors += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1

    # Clean up stale federated files from removed projects
    # Only removes files that contain the federation marker comment,
    # so hand-maintained or auxiliary files are never deleted.
    if not filter_name:
        known_names = {p.get("name") for p in projects if isinstance(p, dict) and p.get("name")}
        stale = 0
        for fname in os.listdir(SYSTEMS_DIR):
            stem = os.path.splitext(fname)[0]
            if stem not in known_names and fname != ".gitkeep":
                stale_path = os.path.join(SYSTEMS_DIR, fname)
                # Only remove files created by federation (marker-based)
                try:
                    with open(stale_path, "r", encoding="utf-8") as f:
                        first_line = f.readline()
                    if not any(m in first_line for m in FEDERATION_MARKERS):
                        continue  # not a federated file, skip
                except (IOError, UnicodeDecodeError):
                    continue  # can't read, skip
                os.remove(stale_path)
                stale += 1
                print(f"  CLEAN: Removed stale {stale_path}")
        if stale:
            print(f"  Cleaned {stale} stale file(s)")

    print(f"\n{'='*40}")
    print(f"Federated: {success} projects, {errors} errors")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Federate architecture from project repos")
    parser.add_argument("--repo", type=str, help="Filter by repo name")
    args = parser.parse_args()
    federate(args.repo)
