"""Collect plugin folders as plain folders, not packages: pytest would otherwise import a plugin's __init__.py by its
folder name, which a hyphen (swim-stroke-rate) makes invalid, so its relative imports fail. The plugin registry
imports it properly (as svc_plugin_<name>)."""
import pytest


def pytest_collect_directory(path, parent):
    if (path / "__init__.py").is_file():
        return pytest.Dir.from_parent(parent, path=path)
