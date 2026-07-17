# SXM Orientation Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Prevent vertically inverted SXM figures by making scan direction, target frame, array flips, and plotting origin one explicit contract.

**Architecture:** Add a structured `SXMMapView` and `prepare_sxm_map()` in `analystm.dataset_utils`. Preserve the legacy helper through the new implementation, then update the STM skill and IO/data-contract references to use the structured API.

**Tech Stack:** Python 3.10+, NumPy, pytest, Markdown skill references.

## Global Constraints

- Raw-to-physical-y-up uses `down=flipud`, `up=no y flip`.
- Backward additionally uses `fliplr`.
- `physical_xy` pairs with `origin="lower"`; `nanonis_display` pairs with `origin="upper"`.
- Preserve existing `normalize_sxm_direction_map()` behavior.
- Do not include private experiment data in reusable tests or skill files.

---

### Task 1: Define the failing orientation contract

**Files:**
- Modify: `tests/test_io_contracts.py`

**Interfaces:**
- Consumes: existing `analystm.dataset_utils` module.
- Produces: expected `prepare_sxm_map(data_obj, direction, header, frame)` behavior.

- [ ] Add synthetic 2×2 numeric corner tests for down/up and forward/backward.
- [ ] Assert `data_yx`, `plot_origin`, `scan_dir`, `direction`, `x_flip`, and `y_flip`.
- [ ] Run the focused tests and confirm failure because the API is absent.

### Task 2: Implement the explicit API

**Files:**
- Modify: `src/analystm/dataset_utils.py`
- Modify: `src/analystm/__init__.py`
- Modify: `scripts/validate_package.py`

**Interfaces:**
- Produces: immutable `SXMMapView` and `prepare_sxm_map()`.
- Preserves: `normalize_sxm_direction_map()` output for every existing caller.

- [ ] Add minimal dataclass and frame validation.
- [ ] Implement physical and Nanonis-display transforms.
- [ ] Route the legacy helper through `frame="nanonis_display"`.
- [ ] Run focused tests to green, then run legacy crop/display tests.

### Task 3: Close the skill documentation gap

**Files:**
- Modify: `SKILL.md`
- Modify: `references/format-io-matrix.md`
- Modify: `references/data-contracts.md`
- Modify: `references/quality-checks.md`

**Interfaces:**
- Consumes: `prepare_sxm_map()` metadata.
- Produces: mandatory report-facing SXM orientation gate and a single correct Python recipe.

- [ ] Add the down/up truth table and target-frame decision to the skill.
- [ ] Replace the bare-array SXM example with the structured API.
- [ ] Require orientation provenance and validation before averaging or coordinate claims.

### Task 4: Validate, synchronize, and publish

**Files:**
- Verify: repository and installed skill trees.

- [ ] Run focused tests and the complete pytest suite.
- [ ] Run package/skill validators.
- [ ] Synchronize the installed skill through `scripts/sync_installed_skill.py` and probe it.
- [ ] Review the exact diff and stage only intended files.
- [ ] Commit the fix, fast-forward local `main`, and push `origin/main`.
