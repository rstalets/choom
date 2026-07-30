try:
    from endpaper._version import __version__
except ImportError:  # running from a source checkout, not a built package
    __version__ = "0.0.0"
