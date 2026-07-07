import importlib

import numpy as np


class _LazyModule:
    def __init__(self, module_name):
        self._module_name = str(module_name)
        self._module = None

    def _load(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, name):
        return getattr(self._load(), name)


signal = _LazyModule("scipy.signal")


IGOR_FFT_WINDOW_NAMES = [
    "Bartlett",
    "Blackman367",
    "Blackman361",
    "Blackman492",
    "Blackman474",
    "Cos1",
    "Cos2",
    "Cos3",
    "Cos4",
    "KaiserBessel20",
    "KaiserBessel25",
    "KaiserBessel30",
    "Hamming",
    "Hanning",
    "Parzen",
    "Poisson2",
    "Poisson3",
    "Poisson4",
    "Riemann",
    "SFT3F",
    "SFT3M",
    "FTNI",
    "SFT4F",
    "SFT5F",
    "SFT4M",
    "FTHP",
    "HFT70",
    "FTSRS",
    "SFT5M",
    "HFT90D",
    "HFT95",
    "HFT116D",
    "HFT144D",
    "HFT169D",
    "HFT196D",
    "HFT223D",
    "HFT248D",
    "none",
]

IGOR_GENERAL_COSINE_WINDOWS = {
    "Blackman367": [0.42323, 0.49755, 0.07922],
    "Blackman361": [0.44959, 0.49364, 0.05677],
    "Blackman492": [0.35875, 0.48829, 0.14128, 0.01168],
    "Blackman474": [0.40217, 0.49703, 0.09392, 0.00183],
    "SFT3F": [0.26526, 0.5, 0.23474],
    "SFT3M": [0.28235, 0.52105, 0.19659],
    "FTNI": [0.2810639, 0.5208972, 0.1980399],
    "SFT4F": [0.21706, 0.42103, 0.28294, 0.07897],
    "SFT5F": [0.1881, 0.36923, 0.28702, 0.13077, 0.02488],
    "SFT4M": [0.241906, 0.460841, 0.255381, 0.041872],
    "FTHP": [1.0, 1.912510941, 1.079173272, 0.1832630879],
    "HFT70": [1.0, 1.90796, 1.07349, 0.18199],
    "FTSRS": [1.0, 1.93, 1.29, 0.388, 0.028],
    "SFT5M": [0.209671, 0.407331, 0.281225, 0.092669, 0.0091036],
    "HFT90D": [1.0, 1.942604, 1.340318, 0.440811, 0.043097],
    "HFT95": [1.0, 1.9383379, 1.3045202, 0.4028270, 0.0350665],
    "HFT116D": [1.0, 1.9575375, 1.4780705, 0.6367431, 0.1228389, 0.0066288],
    "HFT144D": [1.0, 1.96760033, 1.57983607, 0.81123644, 0.22583558, 0.02773848, 0.00090360],
    "HFT169D": [1.0, 1.97441842, 1.65409888, 0.95788187, 0.33673420, 0.06364621, 0.00521942, 0.00010599],
    "HFT196D": [1.0, 1.979280420, 1.710288951, 1.081629853, 0.448734314, 0.112376628, 0.015122992, 0.000871252, 0.000011896],
    "HFT223D": [1.0, 1.98298997309, 1.75556083063, 1.19037717712, 0.56155440797, 0.17296769663, 0.03233247087, 0.00324954578, 0.00013801040, 0.00000132725],
    "HFT248D": [1.0, 1.985844164102, 1.791176438506, 1.282075284005, 0.667777530266, 0.240160796576, 0.056656381764, 0.008134974479, 0.000624544650, 0.000019808998, 0.000000132974],
}

IGOR_POWER_COSINE_WINDOWS = {
    "Cos1": 1,
    "Cos2": 2,
    "Cos3": 3,
    "Cos4": 4,
}

IGOR_WINDOW_ALIASES = {
    "": "none",
    "off": "none",
    "false": "none",
    "none": "none",
    "hann": "Hanning",
    "hanning": "Hanning",
    "cosine": "Cos1",
    "blackman": "Blackman367",
}
IGOR_WINDOW_ALIASES.update({name.lower(): name for name in IGOR_FFT_WINDOW_NAMES})


def _fft_window_tooltip(name):
    if name == "none":
        return "Igor FFT window: none"
    if name in IGOR_POWER_COSINE_WINDOWS:
        return f"Igor FFT window: cosine power window (alpha={IGOR_POWER_COSINE_WINDOWS[name]})."
    if name.startswith("KaiserBessel"):
        return f"Igor FFT window: Kaiser-Bessel beta={name.replace('KaiserBessel', '')}."
    if name.startswith("Poisson"):
        return f"Igor FFT window: Poisson alpha={name.replace('Poisson', '')}."
    return f"Igor FFT window: {name}"


FFT_WINDOW_OPTIONS = [(name, _fft_window_tooltip(name)) for name in IGOR_FFT_WINDOW_NAMES]


def canonical_fft_window_name(name):
    key = str(name or "").strip().lower()
    return IGOR_WINDOW_ALIASES.get(key)


def fft_window_1d(n, name):
    n = max(1, int(n))
    if n == 1:
        return np.ones(1, dtype=float)

    win_name = canonical_fft_window_name(name)
    if not win_name or win_name == "none":
        return np.ones(n, dtype=float)
    if win_name == "Bartlett":
        return np.bartlett(n).astype(float, copy=False)
    if win_name == "Hamming":
        return np.hamming(n).astype(float, copy=False)
    if win_name == "Hanning":
        return np.hanning(n).astype(float, copy=False)
    if win_name == "Parzen":
        return signal.windows.parzen(n, sym=True).astype(float, copy=False)
    if win_name == "Riemann":
        x = np.linspace(-1.0, 1.0, n, dtype=float)
        return np.sinc(x)
    if win_name in IGOR_POWER_COSINE_WINDOWS:
        alpha = IGOR_POWER_COSINE_WINDOWS[win_name]
        base = signal.windows.cosine(n, sym=True).astype(float, copy=False)
        return np.power(base, alpha, dtype=float)
    if win_name.startswith("KaiserBessel"):
        beta = float(win_name.replace("KaiserBessel", ""))
        return signal.windows.kaiser(n, beta=beta, sym=True).astype(float, copy=False)
    if win_name.startswith("Poisson"):
        alpha = float(win_name.replace("Poisson", ""))
        x = np.linspace(-1.0, 1.0, n, dtype=float)
        return np.exp(-alpha * np.abs(x))
    coeffs = IGOR_GENERAL_COSINE_WINDOWS.get(win_name)
    if coeffs is not None:
        return signal.windows.general_cosine(n, coeffs, sym=True).astype(float, copy=False)
    return np.ones(n, dtype=float)


def fft_window_2d(shape, name):
    ny, nx = map(int, shape)
    return np.outer(fft_window_1d(ny, name), fft_window_1d(nx, name))


def prepare_fft_input(data, window_name="Hanning"):
    arr = np.asarray(data, dtype=float)
    mean_val = float(np.nanmean(arr))
    if not np.isfinite(mean_val):
        mean_val = 0.0
    arr_fft = np.nan_to_num(arr, nan=mean_val, posinf=mean_val, neginf=mean_val) - mean_val
    win_name = canonical_fft_window_name(window_name)
    if win_name and win_name != "none":
        arr_fft = arr_fft * fft_window_2d(arr_fft.shape, win_name)
    return arr_fft


def build_windowed_fft_complex(data, window_name="Hanning"):
    return np.fft.fftshift(np.fft.fft2(prepare_fft_input(data, window_name=window_name)))


def apply_fft_display_scale(magnitude, mode):
    mag = np.maximum(np.asarray(magnitude, dtype=float), 0.0)
    mode_key = str(mode or "Log").strip().lower()
    if mode_key == "sqrt":
        return np.sqrt(mag)
    if mode_key in ("mag", "linear"):
        return mag
    return np.log(mag + 1e-12)


def axis_centers_to_edges(axis, fallback_step=1.0):
    arr = np.asarray(axis, dtype=float).ravel()
    if arr.size == 0:
        step = float(fallback_step) if np.isfinite(fallback_step) and fallback_step != 0 else 1.0
        half = 0.5 * abs(step)
        return -half, half
    if arr.size == 1:
        step = float(fallback_step) if np.isfinite(fallback_step) and fallback_step != 0 else 1.0
    else:
        diffs = np.diff(arr)
        diffs = diffs[np.isfinite(diffs) & (diffs != 0)]
        if diffs.size:
            step = float(np.median(diffs))
        else:
            step = float(fallback_step) if np.isfinite(fallback_step) and fallback_step != 0 else 1.0
    left = float(arr[0] - 0.5 * step)
    right = float(arr[-1] + 0.5 * step)
    if right < left:
        left, right = right, left
    return left, right


def build_fft_dc_gaussian_notch_2d(shape, sigma_px=1.5, center=None):
    if shape is None or len(shape) < 2:
        return None
    ny, nx = int(shape[0]), int(shape[1])
    if ny <= 0 or nx <= 0:
        return None
    try:
        sigma = float(sigma_px)
    except Exception:
        sigma = 0.0
    if not np.isfinite(sigma) or sigma <= 0.0:
        return np.ones((ny, nx), dtype=float)
    if center is None:
        cy = float(ny // 2)
        cx = float(nx // 2)
    else:
        cy, cx = center
        cy = float(cy)
        cx = float(cx)
    yy, xx = np.ogrid[:ny, :nx]
    rr2 = (yy - cy) ** 2 + (xx - cx) ** 2
    gaussian = np.exp(-0.5 * rr2 / max(sigma * sigma, 1e-18))
    return np.asarray(1.0 - gaussian, dtype=float)


def build_fft_dc_gaussian_notch_1d(length, sigma_px=1.5, center=None):
    n = int(length)
    if n <= 0:
        return None
    try:
        sigma = float(sigma_px)
    except Exception:
        sigma = 0.0
    if not np.isfinite(sigma) or sigma <= 0.0:
        return np.ones(n, dtype=float)
    c = float(n // 2) if center is None else float(center)
    xx = np.arange(n, dtype=float)
    gaussian = np.exp(-0.5 * ((xx - c) ** 2) / max(sigma * sigma, 1e-18))
    return np.asarray(1.0 - gaussian, dtype=float)


def apply_fft_dc_mask(data, radius_px=1.5, center=None, copy=True, sigma_px=None):
    arr = np.array(data, copy=bool(copy))
    if arr.ndim < 2:
        return arr
    sigma = radius_px if sigma_px is None else sigma_px
    notch = build_fft_dc_gaussian_notch_2d(arr.shape[:2], sigma_px=sigma, center=center)
    if notch is None:
        return arr
    if arr.ndim == 2:
        arr *= notch
    else:
        arr *= notch[..., None]
    return arr
