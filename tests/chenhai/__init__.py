"""ChenHai harness tests.

Grouped in a subpackage so the layout mirrors ``skills/chenhai_harness/``.

Discovery note: ``unittest discover`` only recurses into directories that are
importable packages, which is why this ``__init__.py`` exists. Without it these
tests would be silently skipped, and a silently skipped test is worse than a
failing one.
"""
