# PySIDAM Capability Map

This map is the human-readable companion to the machine-readable capability index in `references/pysidam-capability-index.json`. It keeps the skill fast: agents should query or skim the map first, then load only the deeper reference needed by the user request.

## Status Tags

- `HEADLESS_READY`: use directly from `pysidam.core` or an agent bridge without Qt.
- `GUI_WRAPPED_EXTRACT`: algorithm exists inside a Qt module and should be extracted or mirrored through an adapter before routine agent use.
- `GUI_ONLY`: currently useful mainly as desktop UI behavior, not as an agent default.
- `OPTIONAL_DEP`: requires an optional dependency such as `Atom_Identificator_core`, PyQt5, or pyqtgraph.
- `UNSUPPORTED`: do not claim this capability yet.

## Fast Agent Routes

- Raw Nanonis `.dat`, `.sxm`, `.3ds`: use `scripts/pysidam_agent/read_file.py`.
- Quick raw-data or symlink inspection: use `scripts/pysidam_agent/read_file.py --quick` after shell `readlink`/`find -L` checks.
- Basic `.dat` overview plots: use `scripts/pysidam_agent/plot_spectrum.py` and the STS quick card.
- Superconducting gap fitting: use `scripts/pysidam_agent/fit_gap.py`, the bundled `pysidam_agent_core` fitter, and the gap fit quick card.
- Bragg q selection and lock-in phase: use `scripts/pysidam_agent/bragg_phase.py policy`, `inspect-roi`, and `lockin-from-decision`.
- Capability lookup: use `scripts/pysidam_agent/capabilities.py --json`, or filter with `--domain` and `--status`.

## Domain Routing

- `core_io`: Nanonis readers, imported text/IBW readers, PySIDAM NPZ archive contracts, Nanonis export.
- `bias_dataset_contracts`: bias divider, bias unit normalization, 3DS cube preparation, SXM direction normalization.
- `topography`: drift correction, FFT peak refinement, atom or site detection, and map filtering.
- `spectroscopy_fitting`: Dynes and superconducting gap models, point fits, and spectra display.
- `linecut_maps`: gap maps, intensity derivatives, waterfall views, and multipeak fitting.
- `qpi_lockin`: FFT volumes, filters, lock-in phase, PR-QPI/PQPI, and symmetry workflows.
- `sjtm`: Josephson current extraction and superfluid-density proxy calculations.
- `spstm`: spin-polarized map, dI/dV, topography, and QPI contrast workflows.
- `deconvolution`: SIS/NIS point deconvolution, grid deconvolution, trace resampling, and DOS fitting.
- `utility_export`: crop, histogram, path visualization, publication export, and Nanonis writers.

When a domain is `GUI_WRAPPED_EXTRACT`, prefer documenting the exact PySIDAM function/class and required inputs over instantiating windows. Add a new `pysidam_agent` adapter when a task repeats or when speed/token use matters.

`pysidam_agent_core` is the preferred location for repeated headless algorithms that were originally embedded in PySIDAM UI modules. In `v0.2.0`, superconducting gap fitting is the first migrated domain.
