"""A pytest plugin (entry point `pytest11`, loaded wherever sports-video-coach is installed): a folder plugin whose
name is not a Python identifier (`swim-stroke-rate`) is collected as a plain folder, not a package. pytest would
otherwise import its __init__.py as a lone module named `__init__`, so a relative import there (`from .page import
...`) fails collection of the plugin's own tests. The plugin registry imports it properly (as svc_plugin_<name>).
Needs pytest 8+ (pytest_collect_directory, pytest.Dir); on older pytest the hook is optional and does nothing."""
import pytest


@pytest.hookimpl(tryfirst=True, optionalhook=True)
def pytest_collect_directory(path, parent):
    Dir = getattr(pytest, "Dir", None)
    if Dir is not None and not path.name.isidentifier() and (path / "__init__.py").is_file():
        return Dir.from_parent(parent, path=path)
