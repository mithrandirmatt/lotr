"""Compatibility wrapper for `copilot` that delegates implementation to
`pyutils/copilot`.

This keeps existing imports like `import copilot.host_tools` working while the
actual implementation lives under `pyutils/copilot`.
"""
from pathlib import Path
from importlib import import_module

# Compute repository root and the pyutils/copilot implementation path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYUTILS_COPILOT = str(_REPO_ROOT / 'pyutils' / 'copilot')
# Ensure the implementation path is searched for submodules of this package.
if _PYUTILS_COPILOT not in __path__:
	__path__.insert(0, _PYUTILS_COPILOT)

# Import the host_tools module (will resolve from pyutils/copilot)
_host_tools = import_module('copilot.host_tools')
repo_browser = _host_tools.repo_browser
code_search = _host_tools.code_search
read_file = _host_tools.read_file

__all__ = ["repo_browser", "code_search", "read_file"]
