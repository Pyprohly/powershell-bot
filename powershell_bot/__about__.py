
from __future__ import annotations

version_major: int = 3
version_minor: int = 0
version_micro: int = 0
version_extra: str = ''

version_patch: int = version_micro
version_triad: tuple[int, int, int] = (version_major, version_minor, version_micro)
version_string: str = '.'.join(map(str, version_triad)) + version_extra

__version__: str = version_string

__title__: str = 'PowerShell Bot'
__summary__: str = "u/PowerShell-Bot"
__uri__: str = "https://github.com/Pyprohly/powershell-bot"
__url__: str = __uri__
__author__: str = 'Pyprohly'
__email__: str = 'pyprohly@gmail.com'
__license__: str = 'MIT'
__copyright__: str = 'Copyright 2022 Pyprohly'
