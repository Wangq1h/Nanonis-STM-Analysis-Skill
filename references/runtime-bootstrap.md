# Runtime Bootstrap

Use this reference before any data IO, fitting, QPI, SJTM, topography correction, or atom-detection task. The goal is to load proven readers and PySIDAM headless helpers before inventing a workflow.

## Default Probe

From the skill repository, run:

```bash
python3 scripts/resolve_runtime.py --probe
```

This first checks the persistent cache, especially `runtime.json`, and runs `probe_runtime.py` through the cached virtual environment Python. It should be the default in every project directory.

If no cached runtime is ready, inspect the bootstrap command:

```bash
python3 scripts/resolve_runtime.py --bootstrap-command
```

For a portable agent that cannot run the resolver, perform the same checks by reading the user-writable cache `runtime.json`, using its `python` path, and actually importing modules, not only by checking package names.

## Persistent Host Configuration

The skill is portable and must not hard-code host paths. Host-specific defaults live outside the skill, in:

```text
~/.config/stm-sjtm-data-processing/host.json
```

Example schema:

```json
{
  "base_python": "/path/to/python3",
  "pysidam_root": "/path/to/pysidam",
  "default_groups": "headless"
}
```

Agents should treat this file as local machine state. Do not commit it to the skill repository. `resolve_runtime.py` and `bootstrap_runtime.py` use it to avoid rediscovering PySIDAM or rebuilding the runtime for each working directory.

## Safe Bootstrap

When required dependencies are missing and local execution is allowed, prefer the bundled bootstrapper over global package installation:

```bash
python3 scripts/bootstrap_runtime.py --groups headless
```

`headless` expands to `core,nanonis,ibw`. This creates or reuses a per-skill virtual environment under a user-writable cache such as `~/.cache/stm-sjtm-data-processing`, installs the selected dependency groups, probes the resulting runtime, and writes `runtime.json` in the cache. A later task in a different directory should reuse this cache through `resolve_runtime.py --probe`, not bootstrap again.

For installed Codex skills, sync from the source repository with `scripts/sync_installed_skill.py`. The installed directory should not carry `.git` metadata; the source repository remains the Git working copy.

Safety rules:

- Use only user-writable paths.
- Use no sudo, no root, no global `pip`, no `brew`, and no conda base modification.
- Use `--dry-run` before installing when the environment is unfamiliar.
- Use `--no-network --wheelhouse /path/to/wheelhouse` for offline or locked-down installs.
- Use `--pysidam-root /path/to/pysidam` to point at an existing source checkout.
- Use `--pysidam-mode none` when the agent must not clone PySIDAM.
- Prefer the host `pysidam_root` from `host.json` or `runtime.json`; do not rediscover or clone PySIDAM for every new project directory.

The bootstrapper never mutates existing PySIDAM source checkouts. If PySIDAM is not importable and no source root is provided, auto mode may clone `https://github.com/Wangq1h/pysidam.git` into the skill cache and load it as source.

## Default Dependency Tiers

Core analysis:

- `numpy`
- `scipy`
- `skimage`
- `matplotlib`
- `openpyxl`

Native STM IO:

- `pysidam`
- `nanonispy`

Igor/IBW:

- PySIDAM reads `.ibw` through `pysidam.core.import_io` without requiring `igor2`.
- `igorwriter` is needed for `.ibw` export.

UI-wrapped PySIDAM modules:

- `PyQt5.QtCore`
- `pyqtgraph`

These are optional for pure core IO, but many PySIDAM GUI modules import them at module import time. If either fails, avoid importing GUI-heavy modules directly and use `pysidam.core.*` first.

AI atom detection:

- `Atom_Identificator_core`
- Install source described by PySIDAM as `git+https://github.com/Wangq1h/AI4STM.git@v0.1.0` when atom/site detection is requested.

The dependency manifests are:

- `runtime/requirements-core.txt`
- `runtime/requirements-nanonis.txt`
- `runtime/requirements-ibw.txt`
- `runtime/requirements-ai.txt`
- `runtime/requirements-ui.txt`
- `runtime/constraints.txt`

Default bootstrap group:

- `headless`: `core`, `nanonis`, `ibw`

Optional groups:

- `ai`: AI atom/site detection dependencies.
- `ui`: Qt/pyqtgraph dependencies for GUI-wrapped modules.
- `all`: headless plus `ai` and `ui`.

## Loading PySIDAM

Order of attempts:

1. Try `import pysidam`.
2. If it fails, check `--pysidam-root`, `PYSIDAM_ROOT`, and nearby source checkouts containing `pysidam/core/nanonis_io.py`.
3. Add the source root, not the package subdirectory, to `PYTHONPATH` or `sys.path`.
4. Import the needed headless modules:
   - `pysidam.core.nanonis_io`
   - `pysidam.core.dataset_utils`
   - `pysidam.core.import_io`
   - `pysidam.core.bias_utils`
   - `pysidam.core.fft_windowing`
   - `pysidam.core.superconducting_gap_models`

## Git Synchronization

When a PySIDAM source checkout is used:

1. Record `git remote -v`, current branch, current HEAD, and working-tree status.
2. If network access is available, run `git fetch origin --prune`.
3. Record `origin/main` or the upstream branch HEAD.
4. If the checkout is dirty, ahead, behind, or diverged, do not merge or reset it automatically. Use a clean clone or detached worktree at the fetched remote HEAD for source understanding.

## Missing Dependency Policy

- Missing `nanonispy` blocks raw `.3ds`, `.sxm`, and `.dat` reading through the normal PySIDAM/Nanonis path.
- Missing `igorwriter` blocks `.ibw` export, not `.ibw` import through PySIDAM.
- Missing or broken Qt blocks GUI-heavy module imports; it does not block pure core IO and normalization.
- Missing `Atom_Identificator_core` blocks AI atom detection only.
- Report the exact import error and the reduced capability instead of silently switching to an unverified parser.
- If bootstrap fails because of a native wheel, platform library, code-signing, or network issue, preserve the probe output and continue only with capabilities that are actually importable.
