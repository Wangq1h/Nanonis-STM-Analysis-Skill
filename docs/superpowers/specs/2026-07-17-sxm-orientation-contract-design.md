# SXM Orientation Contract Design

## Problem

`normalize_sxm_direction_map()` returns a bare array in a scan-normalized display order. Its name does not reveal the required Matplotlib `origin`, so callers can pair the result with `origin="lower"` and invert a Nanonis down-scan vertically.

## Approved coordinate contract

For a raw nanonispy SXM array rendered in physical Cartesian coordinates with `origin="lower"`:

| Scan direction | Forward y transform | Backward additional transform |
| --- | --- | --- |
| `down` | `flipud` | `fliplr` |
| `up` | none | `fliplr` |

The existing scan-normalized display convention remains available for compatibility:

| Target frame | Plot origin | Purpose |
| --- | --- | --- |
| `physical_xy` | `lower` | Report-facing physical x-right/y-up maps |
| `nanonis_display` | `upper` | Match the Nanonis screen orientation |

## API

Add `prepare_sxm_map()` returning an `SXMMapView` that binds the transformed `(y, x)` array to `frame`, `plot_origin`, `scan_dir`, `direction`, `x_flip`, and `y_flip`. Keep `normalize_sxm_direction_map()` backward compatible, but document it as returning scan-normalized display order and implement it through the explicit API.

## Skill contract

Require every report-facing SXM workflow to declare its target frame. Route new examples through `prepare_sxm_map()` and require provenance for `scan_dir`, direction, flips, origin, and validation status. Do not average forward/backward maps until both use the same verified frame.

## Verification

- Synthetic numeric corner tests cover `down/up × forward/backward`.
- Compatibility tests prove the legacy helper output is unchanged.
- The full repository test suite and package validation pass.
- The installed skill is synchronized from the source checkout and revalidated.
