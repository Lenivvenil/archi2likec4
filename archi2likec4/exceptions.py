"""Domain exceptions for archi2likec4."""


class Archi2LikeC4Error(Exception):
    """Base exception for all archi2likec4 errors."""


class ConfigError(Archi2LikeC4Error):
    """Raised when a configuration value is missing, invalid, or inconsistent."""


class ParseError(Archi2LikeC4Error):
    """Raised when ArchiMate XML cannot be parsed or is structurally invalid."""


class ValidationError(Archi2LikeC4Error):
    """Raised when the built model fails quality-gate validation."""
