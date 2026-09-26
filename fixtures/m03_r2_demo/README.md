# `m03_r2_demo` — synthetic harness fixture

Everything in this directory is synthetic and was written for demonstration and
test purposes.

* No real calibration evidence, matter, or experimental artifact is present.
* No private path, private identifier, or private document is reproduced.
* The `task_id` / `topic` pair (`M03_R2` / `missing_authority`) is used only as
  a shape example. It is not a report of any real run.

## Files

| Path | Purpose |
| --- | --- |
| `task_spec.template.json` | The TaskSpec **shape** example, published verbatim in the documentation. Absolute host paths; not directly runnable. |
| `task_spec.json` | The runnable variant. Contains the placeholder `REPLACED_AT_TEST_TIME` and the workspace-relative source `source/dossier`. The test bootstrap rewrites `workspace_root` into a scratch directory before use. |
| `source/dossier/` | A synthetic input tree, including one nested directory, used to exercise recursive staging. |

## Why two specs

`task_spec.template.json` is the documentation example and is never executed —
it points at an absolute path that does not exist on any machine. The runnable
demo needs a workspace it is allowed to create, so `task_spec.json` carries a
placeholder that the harness tests substitute at run time. Keeping them separate
means no test can accidentally write into a path copied from the documentation.
