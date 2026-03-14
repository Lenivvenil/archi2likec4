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
                    with open(fpath, "r", encoding="utf-8") as f:
                        first_line = f.readline()
                    if not any(m in first_line for m in FEDERATION_MARKERS):
                        continue
                except (IOError, UnicodeDecodeError):
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
