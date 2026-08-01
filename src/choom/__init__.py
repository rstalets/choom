try:
    from choom._version import __version__  # type: ignore[import-untyped]
except ImportError:  # running from a source checkout, not a built package
    __version__ = "0.0.0"

__all__ = ["__version__"]
