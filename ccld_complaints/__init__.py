"""Source-tree package bootstrap for exact repository-root module commands.

The application package remains under ``src/ccld_complaints``.  Extending this package's
search path lets repository-local virtual environments run documented ``python -m``
entry points without a machine-specific editable install or persistent ``PYTHONPATH``.
"""

from pathlib import Path

__version__ = "0.1.0"
__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "ccld_complaints")]
