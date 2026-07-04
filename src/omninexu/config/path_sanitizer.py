"""Cross-platform path utilities for the OmniNexu data root.

Provides :class:`PathSanitizer` -- normalises user-supplied paths.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathSanitizer:
    """Normalise filesystem paths.  All methods are static."""

    @staticmethod
    def sanitize(path_str: str) -> Path:
        """Convert *path_str* to an absolute, resolved ``Path``.

        Expands ``~`` and environment variables.
        """
        expanded = os.path.expandvars(os.path.expanduser(path_str))
        return Path(expanded).resolve()
