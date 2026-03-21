"""archi2likec4 — Convert coArchi XML (ArchiMate) to LikeC4 .c4 files."""

try:
    from importlib.metadata import PackageNotFoundError as _PkgNotFound
    from importlib.metadata import version as _pkg_version
    __version__: str = _pkg_version('archi2likec4')
except _PkgNotFound:
    __version__ = '1.3.0'

from .config import ConvertConfig, load_config
from .exceptions import Archi2LikeC4Error, ConfigError, ParseError, ValidationError
from .pipeline import ConvertResult, convert
from .pipeline import main as run_pipeline

__all__ = [
    '__version__',
    'ConvertConfig',
    'load_config',
    'convert',
    'ConvertResult',
    'run_pipeline',
    'Archi2LikeC4Error',
    'ConfigError',
    'ParseError',
    'ValidationError',
]
