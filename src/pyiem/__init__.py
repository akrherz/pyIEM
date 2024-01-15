"""Python Utilities developed for/by Iowa Environmental Mesonet

Python is an important part of the Iowa Environmental Mesonet (IEM).  This
package is used by many parts of the IEM codebase and hopefully somewhat
useful to others!?!?
"""


def __getattr__(name):
    """Allows some lazy loading of modules."""
    if name == "__version__":
        from ._version import get_version  # noqa: E402

        return get_version()
    raise AttributeError(f"module {__name__} has no attribute {name}")
