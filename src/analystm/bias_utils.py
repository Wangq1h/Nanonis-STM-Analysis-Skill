import numpy as np


BIAS_SLIDER_SUBSTEPS = 20


def normalize_channel_name(name):
    return "".join(ch.lower() for ch in str(name or "") if ch.isalnum())


def is_bias_like_channel_name(name):
    norm = normalize_channel_name(name)
    if not norm:
        return False
    if ("bias" in norm) or ("sweep" in norm):
        return True
    return norm in {
        "v",
        "mv",
        "voltage",
        "voltagev",
        "voltagemv",
        "biascalc",
        "biascalcv",
        "biascalcmv",
        "samplebias",
        "samplebiasv",
    }


def apply_bias_slider_direction(slider, descending):
    """Set slider direction while keeping progress fill on the left side."""
    descending = bool(descending)
    slider.setInvertedAppearance(descending)
    slider.setInvertedControls(descending)
    slider.setStyleSheet(
        "QSlider::sub-page:horizontal { background: #2ea7ff; border-radius: 2px; }"
        "QSlider::add-page:horizontal { background: #d5d5d5; border-radius: 2px; }"
    )


def bias_slider_to_index(slider_value, count, substeps=BIAS_SLIDER_SUBSTEPS):
    try:
        n = int(count)
    except Exception:
        n = 0
    if n <= 0:
        return int(slider_value)
    try:
        steps = max(1, int(substeps))
    except Exception:
        steps = 1
    max_value = max(0, (n - 1) * steps)
    value = int(np.clip(int(round(slider_value)), 0, max_value))
    return int(np.clip(int(np.rint(value / float(steps))), 0, n - 1))


def bias_index_to_slider(bias_idx, count, substeps=BIAS_SLIDER_SUBSTEPS):
    try:
        n = int(count)
    except Exception:
        n = 0
    if n <= 0:
        return int(bias_idx)
    try:
        steps = max(1, int(substeps))
    except Exception:
        steps = 1
    idx = int(np.clip(int(round(bias_idx)), 0, n - 1))
    return int(idx * steps)


def configure_bias_index_slider(slider, count, current_index=0, substeps=BIAS_SLIDER_SUBSTEPS):
    if slider is None:
        return
    try:
        n = int(count)
    except Exception:
        n = 0
    if n <= 0:
        slider.setRange(0, 0)
        slider.setValue(0)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        return
    try:
        steps = max(1, int(substeps))
    except Exception:
        steps = 1
    slider.setRange(0, max(0, (n - 1) * steps))
    slider.setSingleStep(1)
    slider.setPageStep(max(1, steps))
    slider.setValue(bias_index_to_slider(current_index, n, substeps=steps))


def normalize_imported_bias_to_mv(bias_array, force=False):
    """Normalize imported bias axis to mV."""
    if bias_array is None:
        return None
    try:
        arr = np.asarray(bias_array, dtype=float).ravel()
    except Exception:
        return None
    if arr.size == 0:
        return arr
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return arr
    if force:
        return arr * 1e3
    max_abs = float(np.nanmax(np.abs(finite)))
    if max_abs <= 2.5:
        return arr * 1e3
    return arr


def apply_bias_divider_to_mv(bias_array, divider=1.0):
    if bias_array is None:
        return None
    try:
        arr = np.asarray(bias_array, dtype=float).ravel()
    except Exception:
        return None
    if arr.size == 0:
        return arr
    try:
        div = float(divider)
    except Exception:
        div = 1.0
    if not np.isfinite(div) or div <= 0:
        div = 1.0
    return arr / div


def normalize_bias_with_divider(bias_array, force=False, divider=1.0, already_mv=False):
    if bias_array is None:
        return None
    try:
        arr = np.asarray(bias_array, dtype=float).ravel()
    except Exception:
        return None
    if arr.size == 0:
        return arr
    if not already_mv:
        arr = normalize_imported_bias_to_mv(arr, force=force)
    return apply_bias_divider_to_mv(arr, divider=divider)


def populate_bias_divider_combo(combo, current=1.0):
    if combo is None:
        return
    try:
        current_val = float(current)
    except Exception:
        current_val = 1.0
    combo.blockSignals(True)
    combo.clear()
    for text, value in (("÷1", 1.0), ("÷10", 10.0), ("÷100", 100.0)):
        combo.addItem(text, value)
    idx = combo.findData(current_val)
    combo.setCurrentIndex(idx if idx >= 0 else 0)
    combo.blockSignals(False)


__all__ = [
    "BIAS_SLIDER_SUBSTEPS",
    "is_bias_like_channel_name",
    "normalize_channel_name",
    "apply_bias_slider_direction",
    "bias_slider_to_index",
    "bias_index_to_slider",
    "configure_bias_index_slider",
    "normalize_imported_bias_to_mv",
    "apply_bias_divider_to_mv",
    "normalize_bias_with_divider",
    "populate_bias_divider_combo",
]
