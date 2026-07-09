# Runtime Bootstrap

Use this reference before any data IO, fitting, QPI, SJTM, topography correction, or atom-site task. The default runtime is AnalySTM-first and headless: it must not require PySIDAM, Qt, pyqtgraph, or a private source checkout.

## Default Probe

From the skill repository, run:

```bash
python3 scripts/resolve_runtime.py --probe
```

This first checks the persistent cache, especially `runtime.json`, and runs `probe_runtime.py` through the cached virtual environment Python. The default probe checks only the public AnalySTM backend plus headless numerical, Nanonis, and IBW-export dependencies. It reports AI atom detection as a planned integration and does not report missing PySIDAM or UI modules.

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
  "default_groups": "headless",
  "include_legacy_pysidam": false
}
```

Agents should treat this file as local machine state. Do not commit it to the skill repository. `resolve_runtime.py` and `bootstrap_runtime.py` use it to avoid rebuilding the runtime for each working directory. Legacy PySIDAM roots are ignored unless `include_legacy_pysidam` is explicitly true.

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
- The default `--pysidam-mode none` must remain in place for normal AnalySTM work.
- Use `--pysidam-mode auto --pysidam-root /path/to/pysidam` only for explicit legacy regression checks.

The bootstrapper never mutates existing PySIDAM source checkouts. If legacy auto mode is explicitly requested and no source root is provided, it may clone `https://github.com/Wangq1h/pysidam.git` into the skill cache and load it as source. This path is outside the default runtime.

## Default Dependency Tiers

Core analysis:

- `analystm`
- `numpy`
- `scipy`
- `skimage`
- `matplotlib`
- `openpyxl`

Native STM IO:

- `nanonispy`

Igor/IBW:

- `igorwriter` is needed for `.ibw` export.

AI atom detection:

- AI detector import is a planned integration, not a default dependency.
- `analystm atom recommend-scale`, `analystm atom lattice-qc`, and `analystm atom wipe-regions` are public headless helpers now.
- External detector probing requires an explicit `--include-ai` runtime probe or `--groups ai` bootstrap.

The dependency manifests are:

- `runtime/requirements-core.txt`
- `runtime/requirements-nanonis.txt`
- `runtime/requirements-ibw.txt`
- `runtime/requirements-ai.txt`
- `runtime/constraints.txt`

Default bootstrap group:

- `headless`: `core`, `nanonis`, `ibw`

Optional groups:

- `ai`: planned external AI atom-detector dependencies; use only when explicitly testing that integration.
- `all`: currently equivalent to `headless`.

## Legacy PySIDAM Checks

PySIDAM is a development reference and legacy fallback, not a public runtime dependency. Only run the legacy probe for explicit regression comparison or source-mapping work:

```bash
python3 scripts/probe_runtime.py --include-legacy-pysidam --pysidam-root /path/to/pysidam
python3 scripts/bootstrap_runtime.py --groups headless --pysidam-mode auto --pysidam-root /path/to/pysidam
```

Do not install Qt or pyqtgraph for agent analysis. GUI-wrapped PySIDAM modules are outside the supported default runtime.

## Git Synchronization

When a legacy PySIDAM source checkout is used:

1. Record `git remote -v`, current branch, current HEAD, and working-tree status.
2. If network access is available, run `git fetch origin --prune`.
3. Record `origin/main` or the upstream branch HEAD.
4. If the checkout is dirty, ahead, behind, or diverged, do not merge or reset it automatically. Use a clean clone or detached worktree at the fetched remote HEAD for source understanding.

## Missing Dependency Policy

- Missing `analystm` blocks public backend execution.
- Missing `nanonispy` blocks raw `.3ds`, `.sxm`, and `.dat` reading through the normal AnalySTM/Nanonis path.
- Missing `igorwriter` blocks `.ibw` export.
- Missing PySIDAM, PyQt5, or pyqtgraph does not reduce default AnalySTM capability.
- Missing `Atom_Identificator_core` means the external AI detector is not connected yet; use scale guidance, lattice QC, and wipe-region helpers that already ship in AnalySTM.
- Report the exact import error and the reduced capability instead of silently switching to an unverified parser.
- If bootstrap fails because of a native wheel, platform library, code-signing, or network issue, preserve the probe output and continue only with capabilities that are actually importable.
