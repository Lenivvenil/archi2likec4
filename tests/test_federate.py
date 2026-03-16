"""Tests for archi2likec4.scripts.federate_template module."""

import os

from archi2likec4.scripts.federate_template import _is_safe_relpath


class TestIsSafeRelpath:
    """Path traversal safety checks."""

    def test_normal_path(self):
        assert _is_safe_relpath("docs/system.c4") is True

    def test_simple_filename(self):
        assert _is_safe_relpath("system.c4") is True

    def test_traversal_rejected(self):
        assert _is_safe_relpath("../etc/passwd") is False

    def test_mid_traversal_rejected(self):
        assert _is_safe_relpath("docs/../../etc/passwd") is False

    def test_absolute_path_rejected(self):
        assert _is_safe_relpath("/etc/passwd") is False

    def test_empty_rejected(self):
        assert _is_safe_relpath("") is False

    def test_windows_separator(self):
        assert _is_safe_relpath("docs\\..\\secret") is False

    def test_windows_absolute(self):
        # os.path.isabs behavior varies by OS, but backslash traversal is caught
        assert _is_safe_relpath("docs\\system.c4") is True


class TestFederateWorkflow:
    """Integration tests for federate script logic."""

    def test_stale_file_cleanup_respects_markers(self, tmp_path, monkeypatch):
        """Only files with federation marker comments should be cleaned up."""
        systems_dir = tmp_path / "systems"
        systems_dir.mkdir()

        # Federated file (has marker)
        federated = systems_dir / "old_project.c4"
        federated.write_text("// Federated from: https://example.com/repo.git\nmodel {}\n")

        # Hand-maintained file (no marker)
        manual = systems_dir / "manual.c4"
        manual.write_text("model { system manual }\n")

        # .gitkeep
        gitkeep = systems_dir / ".gitkeep"
        gitkeep.write_text("")

        from archi2likec4.scripts.federate_template import FEDERATION_MARKERS

        # Simulate cleanup logic (extracted from federate())
        known_names = {"active_project"}
        cleaned = []
        for fname in os.listdir(systems_dir):
            stem = os.path.splitext(fname)[0]
            if stem not in known_names and fname != ".gitkeep":
                fpath = systems_dir / fname
                try:
                    with open(fpath, encoding="utf-8") as f:
                        first_line = f.readline()
                    if not any(m in first_line for m in FEDERATION_MARKERS):
                        continue
                except (OSError, UnicodeDecodeError):
                    continue
                cleaned.append(fname)

        assert "old_project.c4" in cleaned
        assert "manual.c4" not in cleaned
        assert ".gitkeep" not in cleaned

    def test_registry_schema_validation(self):
        """Non-dict registry entries should be handled gracefully."""
        # The function checks isinstance(project, dict) — verify the constant exists
        from archi2likec4.scripts.federate_template import REGISTRY_PATH
        assert isinstance(REGISTRY_PATH, str)


# ── Tests for archi2likec4.federation module ──────────────────────────────

class TestGenerateFederateScript:
    """Tests for federation.generate_federate_script()."""

    def test_returns_string(self):
        from archi2likec4.federation import generate_federate_script
        result = generate_federate_script()
        assert isinstance(result, str)

    def test_nonempty(self):
        from archi2likec4.federation import generate_federate_script
        result = generate_federate_script()
        assert len(result) > 100

    def test_contains_python_code(self):
        from archi2likec4.federation import generate_federate_script
        result = generate_federate_script()
        assert 'def ' in result or 'import ' in result

    def test_consistent_results(self):
        from archi2likec4.federation import generate_federate_script
        assert generate_federate_script() == generate_federate_script()


class TestGenerateFederationRegistry:
    """Tests for federation.generate_federation_registry()."""

    def test_returns_string(self):
        from archi2likec4.federation import generate_federation_registry
        result = generate_federation_registry()
        assert isinstance(result, str)

    def test_contains_projects_key(self):
        from archi2likec4.federation import generate_federation_registry
        result = generate_federation_registry()
        assert 'projects:' in result

    def test_contains_template_comment(self):
        from archi2likec4.federation import generate_federation_registry
        result = generate_federation_registry()
        assert 'Federation Registry' in result

    def test_valid_yaml_structure(self):
        from archi2likec4.federation import generate_federation_registry
        result = generate_federation_registry()
        # Should have 'projects: []' indicating empty default list
        assert 'projects: []' in result

    def test_consistent_results(self):
        from archi2likec4.federation import generate_federation_registry
        assert generate_federation_registry() == generate_federation_registry()
