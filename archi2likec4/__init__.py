"""archi2likec4 — Convert coArchi XML (ArchiMate) to LikeC4 .c4 files."""

__version__ = '1.1.0'

from .config import ConvertConfig, load_config
from .pipeline import main as run_pipeline

__all__ = ['__version__', 'ConvertConfig', 'load_config', 'run_pipeline']
