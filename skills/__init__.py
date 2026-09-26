"""ChenHai Skill package namespace.

This package exists so that the ChenHai evidence discipline harness is
importable from a clean checkout without an install, and so that this
repository's layout matches the other SeaFlow Skill repositories::

    skills/chenhai_harness/     the harness runtime
    tests/                      the suite, runnable with pytest or unittest

Keep it empty. Import paths such as ``skills.chenhai_harness`` must keep working
when this repository is vendored, so no path manipulation, no re-export and no
side effect belongs here.
"""
