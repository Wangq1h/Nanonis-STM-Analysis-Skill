from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from scipy import ndimage
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit, least_squares
from scipy.signal import find_peaks, savgol_filter

HAS_MULTIPEAK_BACKEND = True
KB_MEV_PER_K = 8.617333262e-2
THERMAL_FWHM_FACTOR = 3.5
GAUSSIAN_FWHM_TO_SIGMA = 1.0 / 2.3548200450309493
GAUSSIAN_PROFILE = "gaussian"
LORENTZIAN_PROFILE = "lorentzian"
BACKGROUND_OFFSET = "offset"
BACKGROUND_FULL_TRACE_LINEAR = "full_trace_linear"
BACKGROUND_IGOR_CUBIC = "igor_cubic"
MAX_MULTIPEAK_COUNT = 32


def _raw_signal_display_range(*series):
    """Return a y-axis range in the same scale as the supplied raw signal."""
    finite_parts = []
    for arr in series:
        vals = np.asarray(arr, dtype=float).ravel()
        vals = vals[np.isfinite(vals)]
        if vals.size:
            finite_parts.append(vals)
    if not finite_parts:
        return -1.0, 1.0

    merged = np.concatenate(finite_parts)
    lo = float(np.min(merged))
    hi = float(np.max(merged))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return -1.0, 1.0

    span = abs(hi - lo)
    ref = max(abs(lo), abs(hi), span)
    if ref <= np.finfo(float).tiny:
        return -1.0, 1.0

    if span <= np.finfo(float).eps * max(ref, 1.0):
        pad = max(0.10 * ref, np.finfo(float).tiny)
    else:
        pad = max(0.08 * span, 1e-6 * ref)
    return min(lo, hi) - pad, max(lo, hi) + pad


def _normalize_peak_profile(profile):
    text = str(profile or GAUSSIAN_PROFILE).strip().lower()
    if text.startswith("lor"):
        return LORENTZIAN_PROFILE
    return GAUSSIAN_PROFILE


def _normalize_background_mode(mode):
    text = str(mode or BACKGROUND_OFFSET).strip().lower().replace("-", "_").replace(" ", "_")
    if text.startswith("off"):
        return BACKGROUND_OFFSET
    if ("cubic" in text) or ("poly3" in text) or ("igor" in text) or text == "bl":
        return BACKGROUND_IGOR_CUBIC
    if (
        ("full" in text and "linear" in text)
        or text.startswith("lin")
        or text.startswith("whole")
        or text.startswith("sym")
        or text.startswith("global")
    ):
        return BACKGROUND_FULL_TRACE_LINEAR
    return BACKGROUND_OFFSET


def _peak_width_label(profile):
    return "gamma" if _normalize_peak_profile(profile) == LORENTZIAN_PROFILE else "sigma"


def _background_mode_label(mode):
    bg_mode = _normalize_background_mode(mode)
    if bg_mode == BACKGROUND_FULL_TRACE_LINEAR:
        return "Global slope + local offset"
    if bg_mode == BACKGROUND_IGOR_CUBIC:
        return "Igor cubic baseline"
    return "Offset only"


@dataclass
class PeakFitResult:
    amps: np.ndarray
    centers: np.ndarray
    sigmas: np.ndarray
    offset: float
    bg_slope: float
    chi2: float
    r2: float
    success: bool
    message: str
    peak_valid: Optional[np.ndarray] = None
    peak_snr: Optional[np.ndarray] = None
    amp_threshold: float = np.nan
    peak_profile: str = GAUSSIAN_PROFILE
    background_mode: str = BACKGROUND_OFFSET
    bg_poly_coeffs: Optional[np.ndarray] = None
    bg_x_center: float = np.nan
    bg_x_scale: float = np.nan
    fit_min: float = np.nan
    fit_max: float = np.nan


class UniversalVortexFitterEngine:
    def __init__(
        self,
        bias,
        position,
        data,
        log_fn: Optional[Callable[[str], None]] = None,
        process_events: Optional[Callable[[], None]] = None,
    ):
        # Bias is normalized to mV by the window before engine construction.
        # Keep it as-is here to avoid accidental double conversion on narrow-range data.
        self.bias = np.asarray(bias, dtype=float).ravel()
        self.pos = np.asarray(position, dtype=float).ravel()
        self.data_raw = np.asarray(data, dtype=float)
        if self.data_raw.ndim != 2:
            raise ValueError("Input data must be 2D: [position, bias].")
        if self.bias.size != self.data_raw.shape[1]:
            raise ValueError("Bias axis length must match data columns.")

        peak = float(np.nanmax(np.abs(self.data_raw))) if self.data_raw.size else 0.0
        self.scale_factor = 10.0 / peak if peak > 0 else 1.0
        self.data = self.data_raw * self.scale_factor

        self.n_pos = self.data.shape[0]
        self.fit_results = [None] * self.n_pos
        self.extracted_peaks = {}
        self.quality = np.full(self.n_pos, np.nan, dtype=float)
        self.last_peak_profile = GAUSSIAN_PROFILE
        self.last_background_mode = BACKGROUND_OFFSET

        self._log_fn = log_fn
        self._process_events = process_events

    def _log(self, msg: str):
        if self._log_fn is not None:
            self._log_fn(msg)

    @staticmethod
    def gaussian(x, amp, center, sigma):
        sigma = float(max(abs(sigma), 1e-8))
        return amp * np.exp(-((x - center) ** 2) / (2.0 * sigma * sigma))

    @staticmethod
    def lorentzian(x, amp, center, sigma):
        gamma = float(max(abs(sigma), 1e-8))
        return float(amp) * (gamma * gamma) / (((np.asarray(x, dtype=float) - float(center)) ** 2) + gamma * gamma)

    @classmethod
    def _peak_model(cls, x, amp, center, sigma, peak_profile=GAUSSIAN_PROFILE):
        profile = _normalize_peak_profile(peak_profile)
        if profile == LORENTZIAN_PROFILE:
            return cls.lorentzian(x, amp, center, sigma)
        return cls.gaussian(x, amp, center, sigma)

    @staticmethod
    def _igor_cubic_reference(fit_range=None, x=None):
        if fit_range is not None:
            xmin = float(min(fit_range))
            xmax = float(max(fit_range))
        else:
            xv = np.asarray(x if x is not None else [], dtype=float).ravel()
            xv = xv[np.isfinite(xv)]
            if xv.size == 0:
                return 0.0, 1.0
            xmin = float(np.nanmin(xv))
            xmax = float(np.nanmax(xv))
        center = 0.5 * (xmin + xmax)
        width = max(abs(xmax - xmin), 1e-8)
        return float(center), float(width)

    @staticmethod
    def _legacy_linear_from_cubic(bg_poly_coeffs, bg_x_center=0.0, bg_x_scale=1.0):
        coeffs = np.asarray(bg_poly_coeffs if bg_poly_coeffs is not None else [], dtype=float).ravel()
        if coeffs.size < 4 or not np.all(np.isfinite(coeffs[:4])):
            return 0.0, 0.0
        x_scale = float(abs(bg_x_scale))
        if not np.isfinite(x_scale) or x_scale < 1e-12:
            x_scale = 1.0
        xprime0 = (0.0 - float(bg_x_center)) / x_scale
        offset = coeffs[0] + coeffs[1] * xprime0 + coeffs[2] * (xprime0 ** 2) + coeffs[3] * (xprime0 ** 3)
        slope = (coeffs[1] + 2.0 * coeffs[2] * xprime0 + 3.0 * coeffs[3] * (xprime0 ** 2)) / x_scale
        return float(slope), float(offset)

    @staticmethod
    def _background_model(
        x,
        offset=0.0,
        bg_slope=0.0,
        bg_poly_coeffs=None,
        bg_x_center=0.0,
        bg_x_scale=1.0,
    ):
        xv = np.asarray(x, dtype=float)
        coeffs = np.asarray(bg_poly_coeffs if bg_poly_coeffs is not None else [], dtype=float).ravel()
        if coeffs.size >= 4 and np.all(np.isfinite(coeffs[:4])):
            x_scale = float(abs(bg_x_scale))
            if not np.isfinite(x_scale) or x_scale < 1e-12:
                x_scale = 1.0
            xprime = (xv - float(bg_x_center)) / x_scale
            return (
                coeffs[0]
                + coeffs[1] * xprime
                + coeffs[2] * (xprime ** 2)
                + coeffs[3] * (xprime ** 3)
            )
        return float(offset) + float(bg_slope) * xv

    @staticmethod
    def _fit_window_from_metadata(fit_min=np.nan, fit_max=np.nan, bg_x_center=np.nan, bg_x_scale=np.nan):
        fit_min = float(fit_min)
        fit_max = float(fit_max)
        if np.isfinite(fit_min) and np.isfinite(fit_max) and fit_max > fit_min:
            return fit_min, fit_max
        center = float(bg_x_center)
        scale = float(abs(bg_x_scale))
        if np.isfinite(center) and np.isfinite(scale) and scale > 1e-12:
            half_width = 0.5 * scale
            return center - half_width, center + half_width
        return None

    @classmethod
    def _mask_curve_to_fit_window(cls, x, y, fit_window):
        arr = np.asarray(y, dtype=float).copy()
        if fit_window is None:
            return arr
        xv = np.asarray(x, dtype=float).ravel()
        if arr.shape != xv.shape:
            return arr
        fit_min = float(min(fit_window))
        fit_max = float(max(fit_window))
        valid = np.isfinite(xv) & (xv >= fit_min) & (xv <= fit_max)
        arr[~valid] = np.nan
        return arr

    def _sum_model(
        self,
        x,
        amps,
        centers,
        sigmas,
        offset=0.0,
        bg_slope=0.0,
        bg_poly_coeffs=None,
        bg_x_center=0.0,
        bg_x_scale=1.0,
        peak_profile=GAUSSIAN_PROFILE,
    ):
        y = self._background_model(
            x,
            offset=offset,
            bg_slope=bg_slope,
            bg_poly_coeffs=bg_poly_coeffs,
            bg_x_center=bg_x_center,
            bg_x_scale=bg_x_scale,
        )
        for a, c, s in zip(amps, centers, sigmas):
            y += self._peak_model(x, a, c, s, peak_profile=peak_profile)
        return y

    @classmethod
    def _despike_signal(cls, y, median_size=5):
        arr = np.asarray(y, dtype=float).ravel()
        if arr.size < 5:
            return np.asarray(arr, dtype=float)
        med_size = int(max(3, median_size))
        if med_size > arr.size:
            med_size = arr.size if arr.size % 2 == 1 else max(3, arr.size - 1)
        if med_size < 3:
            return np.asarray(arr, dtype=float)
        try:
            median = np.asarray(ndimage.median_filter(arr, size=med_size, mode="nearest"), dtype=float)
        except Exception:
            return np.asarray(arr, dtype=float)
        resid = np.asarray(arr - median, dtype=float)
        noise = max(cls._robust_noise(resid), 1e-8)
        try:
            span = float(np.nanpercentile(arr, 95) - np.nanpercentile(arr, 5))
        except Exception:
            span = float(np.nanmax(arr) - np.nanmin(arr))
        span = max(span, 1e-8)
        spike_thr = max(4.5 * noise, 0.018 * span, 1e-8)
        out = np.asarray(arr, dtype=float).copy()
        mask = np.abs(resid) > spike_thr
        out[mask] = median[mask]
        return out

    @classmethod
    def _estimate_linear_background(cls, x, y, fit_range=None):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        if n < 4:
            y0 = float(np.nanmedian(y_arr[:n])) if n > 0 and np.any(np.isfinite(y_arr[:n])) else 0.0
            return 0.0, y0
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        if fit_range is not None:
            fit_min = float(min(fit_range))
            fit_max = float(max(fit_range))
            finite &= (x_arr >= fit_min) & (x_arr <= fit_max)
        if np.count_nonzero(finite) < 4:
            finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        if np.count_nonzero(finite) < 4:
            y0 = float(np.nanmedian(y_arr[finite])) if np.any(finite) else 0.0
            return 0.0, y0
        x_fit = np.asarray(x_arr[finite], dtype=float)
        y_fit = np.asarray(y_arr[finite], dtype=float)
        order = np.argsort(x_fit)
        x_fit = np.asarray(x_fit[order], dtype=float)
        y_fit = cls._despike_signal(np.asarray(y_fit[order], dtype=float))
        m = int(x_fit.size)
        if m < 4:
            y0 = float(np.nanmedian(y_fit)) if y_fit.size and np.any(np.isfinite(y_fit)) else 0.0
            return 0.0, y0
        try:
            y_span = float(np.nanpercentile(y_fit, 95) - np.nanpercentile(y_fit, 5))
        except Exception:
            y_span = float(np.nanmax(y_fit) - np.nanmin(y_fit))
        y_span = max(y_span, 1e-8)

        smooth = np.asarray(y_fit, dtype=float)
        if m >= 7:
            bg_win = int(np.clip(np.ceil(0.18 * m), 7, 61))
            if bg_win % 2 == 0:
                bg_win += 1
            if bg_win >= m:
                bg_win = m if (m % 2 == 1) else (m - 1)
            if bg_win >= 5:
                try:
                    smooth = savgol_filter(y_fit, window_length=bg_win, polyorder=min(3, bg_win - 2))
                except Exception:
                    smooth = np.asarray(y_fit, dtype=float)
        resid_smooth = np.asarray(y_fit - smooth, dtype=float)
        noise0 = max(cls._robust_noise(resid_smooth), 1e-8)
        peak_thr = max(1.75 * noise0, 0.015 * y_span, 1e-8)
        base_weights = np.ones_like(y_fit, dtype=float)
        base_weights[resid_smooth > peak_thr] = 0.18

        def _weighted_line(weights):
            w = np.sqrt(np.clip(np.asarray(weights, dtype=float), 1e-6, None))
            A = np.column_stack((x_fit * w, w))
            b = y_fit * w
            coef, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
            return float(coef[0]), float(coef[1])

        try:
            slope, intercept = _weighted_line(base_weights)
            for _ in range(8):
                model = slope * x_fit + intercept
                resid = np.asarray(y_fit - model, dtype=float)
                neg = resid[resid < 0]
                sigma = cls._robust_noise(neg) if neg.size >= 3 else cls._robust_noise(resid)
                sigma = max(float(sigma), 0.0025 * y_span, 1e-8)
                center = 2.0 * sigma
                scale = max(0.5 * sigma, 1e-8)
                asym = 1.0 / (1.0 + np.exp(np.clip((resid - center) / scale, -40.0, 40.0)))
                weights = np.clip(base_weights * asym, 0.03, 1.0)
                new_slope, new_intercept = _weighted_line(weights)
                if (
                    abs(new_slope - slope) <= 1e-10 * max(1.0, abs(slope))
                    and abs(new_intercept - intercept) <= 1e-8 * max(1.0, abs(intercept))
                ):
                    slope, intercept = new_slope, new_intercept
                    break
                slope, intercept = new_slope, new_intercept
            if np.isfinite(slope) and np.isfinite(intercept):
                return float(slope), float(intercept)
        except Exception:
            pass
        y0 = float(np.nanmedian(y_fit)) if y_fit.size and np.any(np.isfinite(y_fit)) else 0.0
        return 0.0, y0

    @classmethod
    def _background_keep_mask(
        cls,
        x,
        y,
        centers=None,
        widths=None,
        fit_range=None,
        peak_profile=GAUSSIAN_PROFILE,
    ):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        if n < 4:
            return np.isfinite(x_arr[:n]) & np.isfinite(y_arr[:n])
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        keep = np.isfinite(x_arr) & np.isfinite(y_arr)
        if fit_range is not None:
            fit_min = float(min(fit_range))
            fit_max = float(max(fit_range))
            keep &= (x_arr >= fit_min) & (x_arr <= fit_max)
        if np.count_nonzero(keep) < 4:
            return np.isfinite(x_arr) & np.isfinite(y_arr)

        centers_arr = np.asarray(centers if centers is not None else [], dtype=float).ravel()
        widths_arr = np.asarray(widths if widths is not None else [], dtype=float).ravel()
        valid_peaks = np.isfinite(centers_arr) & np.isfinite(widths_arr) & (widths_arr > 0)
        centers_arr = centers_arr[valid_peaks]
        widths_arr = np.abs(widths_arr[valid_peaks])
        if centers_arr.size == 0:
            return np.asarray(keep, dtype=bool)

        x_keep = np.asarray(x_arr[keep], dtype=float)
        span = float(np.nanmax(x_keep) - np.nanmin(x_keep)) if x_keep.size else 0.0
        span = max(span, 1e-6)
        profile = _normalize_peak_profile(peak_profile)
        mask_factor = 6.0 if profile == LORENTZIAN_PROFILE else 4.0
        min_radius = 0.05 * span

        bg_keep = np.asarray(keep, dtype=bool)
        for c, w in zip(centers_arr, widths_arr):
            radius = max(mask_factor * float(w), min_radius)
            bg_keep &= (np.abs(x_arr - float(c)) > radius)

        min_points = max(8, int(np.ceil(0.16 * np.count_nonzero(keep))))
        if np.count_nonzero(bg_keep) >= min_points:
            return np.asarray(bg_keep, dtype=bool)
        return np.asarray(keep, dtype=bool)

    @classmethod
    def _estimate_peak_masked_linear_background(
        cls,
        x,
        y,
        centers=None,
        widths=None,
        fit_range=None,
        peak_profile=GAUSSIAN_PROFILE,
    ):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        if n < 4:
            return cls._estimate_linear_background(x_arr, y_arr, fit_range=fit_range)
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        bg_keep = cls._background_keep_mask(
            x_arr,
            y_arr,
            centers=centers,
            widths=widths,
            fit_range=fit_range,
            peak_profile=peak_profile,
        )
        return cls._estimate_linear_background(x_arr[bg_keep], y_arr[bg_keep], fit_range=None)

    @classmethod
    def _estimate_peak_masked_cubic_background(
        cls,
        x,
        y,
        centers=None,
        widths=None,
        fit_range=None,
        peak_profile=GAUSSIAN_PROFILE,
    ):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        if fit_range is not None:
            fit_min = float(min(fit_range))
            fit_max = float(max(fit_range))
            finite &= (x_arr >= fit_min) & (x_arr <= fit_max)
        x_arr = np.asarray(x_arr[finite], dtype=float)
        y_arr = np.asarray(y_arr[finite], dtype=float)
        if x_arr.size == 0:
            return np.zeros(4, dtype=float), 0.0, 1.0

        bg_keep = cls._background_keep_mask(
            x_arr,
            y_arr,
            centers=centers,
            widths=widths,
            fit_range=None,
            peak_profile=peak_profile,
        )
        if np.count_nonzero(bg_keep) >= 6:
            x_fit = np.asarray(x_arr[bg_keep], dtype=float)
            y_fit = np.asarray(y_arr[bg_keep], dtype=float)
        else:
            x_fit = np.asarray(x_arr, dtype=float)
            y_fit = np.asarray(y_arr, dtype=float)

        order = np.argsort(x_fit)
        x_fit = np.asarray(x_fit[order], dtype=float)
        y_fit = cls._despike_signal(np.asarray(y_fit[order], dtype=float))
        bg_x_center, bg_x_scale = cls._igor_cubic_reference(fit_range=fit_range, x=x_fit)

        fallback = np.zeros(4, dtype=float)
        if y_fit.size and np.any(np.isfinite(y_fit)):
            fallback[0] = float(np.nanmedian(y_fit))
        if x_fit.size < 6:
            return fallback, float(bg_x_center), float(bg_x_scale)

        xprime = (x_fit - float(bg_x_center)) / max(float(bg_x_scale), 1e-8)
        design = np.column_stack((np.ones_like(xprime), xprime, xprime * xprime, xprime * xprime * xprime))

        try:
            y_span = float(np.nanpercentile(y_fit, 95) - np.nanpercentile(y_fit, 5))
        except Exception:
            y_span = float(np.nanmax(y_fit) - np.nanmin(y_fit))
        y_span = max(y_span, 1e-8)

        env = cls._lower_envelope_signal(x_fit, y_fit)
        resid_env = np.asarray(y_fit - env, dtype=float)
        noise0 = max(cls._robust_noise(resid_env), 1e-8)
        peak_thr = max(1.75 * noise0, 0.015 * y_span, 1e-8)
        base_weights = np.ones_like(y_fit, dtype=float)
        base_weights[resid_env > peak_thr] = 0.18

        def _weighted_poly(weights, target):
            w = np.sqrt(np.clip(np.asarray(weights, dtype=float), 1e-6, None))
            Aw = design * w[:, None]
            bw = np.asarray(target, dtype=float) * w
            coef, _, _, _ = np.linalg.lstsq(Aw, bw, rcond=None)
            return np.asarray(coef, dtype=float)

        try:
            coeffs = _weighted_poly(np.ones_like(base_weights, dtype=float), env)
        except Exception:
            coeffs = fallback

        try:
            if not np.all(np.isfinite(coeffs)):
                coeffs = _weighted_poly(base_weights, y_fit)
            for _ in range(8):
                model = design @ coeffs
                resid = np.asarray(y_fit - model, dtype=float)
                neg = resid[resid < 0]
                sigma = cls._robust_noise(neg) if neg.size >= 3 else cls._robust_noise(resid)
                sigma = max(float(sigma), 0.0025 * y_span, 1e-8)
                center_w = 2.0 * sigma
                scale_w = max(0.5 * sigma, 1e-8)
                asym = 1.0 / (1.0 + np.exp(np.clip((resid - center_w) / scale_w, -40.0, 40.0)))
                weights = np.clip(base_weights * asym, 0.03, 1.0)
                new_coeffs = _weighted_poly(weights, y_fit)
                if np.max(np.abs(new_coeffs - coeffs)) <= 1e-8 * max(1.0, float(np.nanmax(np.abs(coeffs)))):
                    coeffs = new_coeffs
                    break
                coeffs = new_coeffs
            if np.all(np.isfinite(coeffs)):
                return np.asarray(coeffs[:4], dtype=float), float(bg_x_center), float(bg_x_scale)
        except Exception:
            pass
        return fallback, float(bg_x_center), float(bg_x_scale)

    @classmethod
    def _estimate_intercept_for_fixed_slope(
        cls,
        x,
        y,
        slope,
        centers=None,
        widths=None,
        fit_range=None,
        peak_profile=GAUSSIAN_PROFILE,
        prefer_edge_anchors=False,
    ):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        if n < 4:
            vals = np.asarray(y_arr[:n], dtype=float) - float(slope) * np.asarray(x_arr[:n], dtype=float)
            return float(np.nanmedian(vals)) if vals.size and np.any(np.isfinite(vals)) else 0.0
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        bg_keep = cls._background_keep_mask(
            x_arr,
            y_arr,
            centers=centers,
            widths=widths,
            fit_range=fit_range,
            peak_profile=peak_profile,
        )
        x_sel = np.asarray(x_arr[bg_keep], dtype=float)
        y_sel = np.asarray(y_arr[bg_keep], dtype=float)
        if prefer_edge_anchors and fit_range is not None and x_sel.size >= 8:
            fit_min = float(min(fit_range))
            fit_max = float(max(fit_range))
            span = max(1e-6, fit_max - fit_min)
            if x_sel.size > 1:
                dx = float(np.nanmedian(np.abs(np.diff(np.sort(x_sel)))))
            else:
                dx = span / 200.0
            if not np.isfinite(dx) or dx <= 0:
                dx = span / 200.0
            edge_w = max(0.18 * span, 8.0 * dx)
            left_mask = (x_sel >= fit_min) & (x_sel <= fit_min + edge_w)
            right_mask = (x_sel >= fit_max - edge_w) & (x_sel <= fit_max)
            edge_mask = left_mask | right_mask
            if np.count_nonzero(left_mask) >= 3 and np.count_nonzero(right_mask) >= 3 and np.count_nonzero(edge_mask) >= 8:
                x_sel = np.asarray(x_sel[edge_mask], dtype=float)
                y_sel = np.asarray(y_sel[edge_mask], dtype=float)
        y_sel = cls._lower_envelope_signal(x_sel, y_sel)
        vals = np.asarray(y_sel, dtype=float) - float(slope) * np.asarray(x_sel, dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            vals = np.asarray(y_arr, dtype=float) - float(slope) * np.asarray(x_arr, dtype=float)
            vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            return 0.0
        intercept = float(np.nanmedian(vals))
        for _ in range(8):
            resid = np.asarray(vals - intercept, dtype=float)
            neg = resid[resid < 0]
            sigma = cls._robust_noise(neg) if neg.size >= 3 else cls._robust_noise(resid)
            sigma = max(float(sigma), 1e-8)
            center = 2.0 * sigma
            scale = max(0.5 * sigma, 1e-8)
            weights = 1.0 / (1.0 + np.exp(np.clip((resid - center) / scale, -40.0, 40.0)))
            weights = np.clip(weights, 0.03, 1.0)
            new_intercept = float(np.sum(weights * vals) / max(np.sum(weights), 1e-8))
            if abs(new_intercept - intercept) <= 1e-8 * max(1.0, abs(intercept)):
                intercept = new_intercept
                break
            intercept = new_intercept
        return float(intercept)

    @classmethod
    def _lower_envelope_signal(cls, x, y):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        if n <= 0:
            return np.zeros(0, dtype=float)
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        x_arr = x_arr[finite]
        y_arr = y_arr[finite]
        if x_arr.size == 0:
            return np.zeros(0, dtype=float)
        order = np.argsort(x_arr)
        x_arr = np.asarray(x_arr[order], dtype=float)
        y_arr = cls._despike_signal(np.asarray(y_arr[order], dtype=float))
        m = int(x_arr.size)
        if m < 7:
            return np.asarray(y_arr, dtype=float)

        bin_count = int(np.clip(np.ceil(m / 18.0), 10, 32))
        edges = np.linspace(float(x_arr[0]), float(x_arr[-1]), bin_count + 1)
        xa = []
        ya = []
        for i in range(bin_count):
            if i == bin_count - 1:
                mask = (x_arr >= edges[i]) & (x_arr <= edges[i + 1])
            else:
                mask = (x_arr >= edges[i]) & (x_arr < edges[i + 1])
            if np.count_nonzero(mask) < 3:
                continue
            xb = np.asarray(x_arr[mask], dtype=float)
            yb = np.asarray(y_arr[mask], dtype=float)
            xa.append(float(np.nanmedian(xb)))
            ya.append(float(np.nanpercentile(yb, 28.0)))
        if len(xa) < 4:
            env = np.asarray(y_arr, dtype=float)
        else:
            xa = np.asarray(xa, dtype=float)
            ya = np.asarray(ya, dtype=float)
            uniq_x, uniq_idx = np.unique(xa, return_index=True)
            uniq_y = ya[uniq_idx]
            if uniq_x.size < 4:
                env = np.asarray(y_arr, dtype=float)
            else:
                env = np.interp(x_arr, uniq_x, uniq_y, left=float(uniq_y[0]), right=float(uniq_y[-1]))

        win = int(np.clip(np.ceil(0.16 * m), 7, 51))
        if win % 2 == 0:
            win += 1
        if win >= m:
            win = m if (m % 2 == 1) else (m - 1)
        if win >= 5:
            try:
                env = savgol_filter(np.asarray(env, dtype=float), window_length=win, polyorder=min(3, win - 2))
            except Exception:
                env = np.asarray(env, dtype=float)
        return np.asarray(env, dtype=float)

    @classmethod
    def _estimate_symmetric_linear_background(
        cls,
        x,
        y,
        centers=None,
        widths=None,
        fit_range=None,
        peak_profile=GAUSSIAN_PROFILE,
        symmetry_hint_range=None,
        intercept_hint_range=None,
    ):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        n = min(x_arr.size, y_arr.size)
        if n < 8:
            return cls._estimate_peak_masked_linear_background(
                x_arr,
                y_arr,
                centers=centers,
                widths=widths,
                fit_range=fit_range,
                peak_profile=peak_profile,
            )
        x_arr = x_arr[:n]
        y_arr = y_arr[:n]
        order = np.argsort(x_arr)
        x_arr = np.asarray(x_arr[order], dtype=float)
        y_arr = cls._despike_signal(np.asarray(y_arr[order], dtype=float))
        bg_keep = np.asarray(
            cls._background_keep_mask(
                x_arr,
                y_arr,
                centers=centers,
                widths=widths,
                fit_range=fit_range,
                peak_profile=peak_profile,
            ),
            dtype=bool,
        )
        if np.count_nonzero(bg_keep) < 8:
            return cls._estimate_peak_masked_linear_background(
                x_arr,
                y_arr,
                centers=centers,
                widths=widths,
                fit_range=fit_range,
                peak_profile=peak_profile,
            )
        x_bg = np.asarray(x_arr[bg_keep], dtype=float)
        y_bg = np.asarray(y_arr[bg_keep], dtype=float)
        if x_bg.size < 8:
            return cls._estimate_peak_masked_linear_background(
                x_arr,
                y_arr,
                centers=centers,
                widths=widths,
                fit_range=fit_range,
                peak_profile=peak_profile,
            )
        y_env = cls._lower_envelope_signal(x_bg, y_bg)
        if x_bg.size > 1:
            dx = float(np.nanmedian(np.abs(np.diff(x_bg))))
        else:
            dx = 0.0
        if not np.isfinite(dx) or dx <= 0:
            span = max(1e-6, float(np.nanmax(x_bg) - np.nanmin(x_bg))) if x_bg.size else 1.0
            dx = span / max(200.0, float(x_arr.size))
        tol = max(1e-8, 0.55 * dx)
        span_bg = max(1e-6, float(np.nanmax(x_bg) - np.nanmin(x_bg))) if x_bg.size else 1.0
        if symmetry_hint_range is not None:
            hint_min = float(min(symmetry_hint_range))
            hint_max = float(max(symmetry_hint_range))
            v_scale = max(abs(hint_min), abs(hint_max), 8.0 * dx, 0.10 * span_bg)
            v_limit = min(float(np.nanmax(np.abs(x_bg))), 2.4 * v_scale)
        else:
            v_scale = max(0.22 * span_bg, 8.0 * dx)
            v_limit = float(np.nanmax(np.abs(x_bg)))
        pair_v = []
        pair_diff = []
        pair_base_w = []
        pos_idx = np.where(x_bg > tol)[0]
        for idx in np.asarray(pos_idx, dtype=int):
            v = float(x_bg[idx])
            if v > v_limit:
                continue
            j = int(np.argmin(np.abs(x_bg + v)))
            if abs(float(x_bg[j]) + v) > tol:
                continue
            if x_bg[j] >= -tol:
                continue
            pair_v.append(v)
            pair_diff.append(float(y_env[idx] - y_env[j]))
            pair_base_w.append(1.0 / (1.0 + (abs(v) / max(v_scale, 1e-8)) ** 4))
        pair_v = np.asarray(pair_v, dtype=float)
        pair_diff = np.asarray(pair_diff, dtype=float)
        pair_base_w = np.asarray(pair_base_w, dtype=float)
        if pair_v.size < 5:
            return cls._estimate_peak_masked_linear_background(
                x_arr,
                y_arr,
                centers=centers,
                widths=widths,
                fit_range=fit_range,
                peak_profile=peak_profile,
            )
        weights = np.clip(pair_base_w, 0.05, 1.0)
        denom = max(2.0 * np.sum(weights * pair_v * pair_v), 1e-8)
        slope = float(np.sum(weights * pair_diff * pair_v) / denom)
        for _ in range(10):
            resid = np.asarray(pair_diff - 2.0 * slope * pair_v, dtype=float)
            sigma = max(cls._robust_noise(resid), 1e-8)
            u = resid / (2.5 * sigma)
            weights = pair_base_w / (1.0 + u * u)
            weights = np.clip(weights, 0.05, 1.0)
            denom = max(2.0 * np.sum(weights * pair_v * pair_v), 1e-8)
            new_slope = float(np.sum(weights * pair_diff * pair_v) / denom)
            if abs(new_slope - slope) <= 1e-10 * max(1.0, abs(slope)):
                slope = new_slope
                break
            slope = new_slope
        anchor_range = intercept_hint_range if intercept_hint_range is not None else fit_range
        intercept = cls._estimate_intercept_for_fixed_slope(
            x_arr,
            y_arr,
            slope=slope,
            centers=centers,
            widths=widths,
            fit_range=anchor_range,
            peak_profile=peak_profile,
            prefer_edge_anchors=anchor_range is not None,
        )
        if not (np.isfinite(slope) and np.isfinite(intercept)):
            return cls._estimate_peak_masked_linear_background(
                x_arr,
                y_arr,
                centers=centers,
                widths=widths,
                fit_range=fit_range,
                peak_profile=peak_profile,
            )
        return float(slope), float(intercept)

    @classmethod
    def _seed_widths_from_centers(cls, centers, fit_range, point_count, fixed_sigma=None):
        centers_arr = np.asarray(centers, dtype=float).ravel()
        n = int(centers_arr.size)
        if n <= 0:
            return np.zeros(0, dtype=float)
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        span = max(1e-6, fit_max - fit_min)
        pts = max(1, int(point_count))
        min_sigma = max(1e-4, span / max(1200.0, 25.0 * pts))
        sigma_seed_cap = max(min_sigma * 2.0, 0.25 * span)
        widths = np.zeros(n, dtype=float)
        for i in range(n):
            dl = centers_arr[i] - centers_arr[i - 1] if i > 0 else np.inf
            dr = centers_arr[i + 1] - centers_arr[i] if i < n - 1 else np.inf
            spacing = min(dl, dr)
            if not np.isfinite(spacing):
                spacing = span / max(2.0, n)
            widths[i] = np.clip(0.2 * spacing, min_sigma, sigma_seed_cap)
        if fixed_sigma is not None and np.isfinite(fixed_sigma):
            widths[:] = np.clip(float(fixed_sigma), min_sigma, sigma_seed_cap)
        return np.asarray(widths, dtype=float)

    @classmethod
    def _prepare_seed_signal(
        cls,
        x,
        y,
        n_peaks,
        fit_range,
        background_mode=BACKGROUND_OFFSET,
        peak_profile=GAUSSIAN_PROFILE,
        fixed_sigma=None,
    ):
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
        finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        x_arr = x_arr[finite]
        y_arr = y_arr[finite]
        if x_arr.size == 0 or y_arr.size == 0:
            return (
                np.zeros(0, dtype=float),
                np.zeros(0, dtype=float),
                np.zeros(0, dtype=float),
                0.0,
                0.0,
            )
        order = np.argsort(x_arr)
        x_arr = np.asarray(x_arr[order], dtype=float)
        y_arr = np.asarray(y_arr[order], dtype=float)

        bg_mode = _normalize_background_mode(background_mode)
        profile = _normalize_peak_profile(peak_profile)
        bg_slope = 0.0
        bg_intercept = 0.0
        y_seed = np.asarray(y_arr, dtype=float)
        if bg_mode == BACKGROUND_IGOR_CUBIC:
            bg_poly_coeffs, bg_x_center, bg_x_scale = cls._estimate_peak_masked_cubic_background(
                x_arr,
                y_arr,
                centers=None,
                widths=None,
                fit_range=fit_range,
                peak_profile=profile,
            )
            y_seed = np.asarray(
                y_arr
                - cls._background_model(
                    x_arr,
                    bg_poly_coeffs=bg_poly_coeffs,
                    bg_x_center=bg_x_center,
                    bg_x_scale=bg_x_scale,
                ),
                dtype=float,
            )
            rough_centers = cls.get_row_initial_guess(
                y=y_seed,
                x=x_arr,
                n_peaks=n_peaks,
                search_range=fit_range,
                fill_to_count=True,
                min_count=1,
            )
            rough_centers = cls._clean_centers(rough_centers, fit_range, max_count=int(max(1, n_peaks)))
            rough_widths = cls._seed_widths_from_centers(
                rough_centers,
                fit_range,
                point_count=x_arr.size,
                fixed_sigma=fixed_sigma,
            )
            bg_poly_coeffs, bg_x_center, bg_x_scale = cls._estimate_peak_masked_cubic_background(
                x_arr,
                y_arr,
                centers=rough_centers,
                widths=rough_widths,
                fit_range=fit_range,
                peak_profile=profile,
            )
            y_seed = np.asarray(
                y_arr
                - cls._background_model(
                    x_arr,
                    bg_poly_coeffs=bg_poly_coeffs,
                    bg_x_center=bg_x_center,
                    bg_x_scale=bg_x_scale,
                ),
                dtype=float,
            )
            bg_slope, bg_intercept = cls._legacy_linear_from_cubic(
                bg_poly_coeffs,
                bg_x_center=bg_x_center,
                bg_x_scale=bg_x_scale,
            )
        if bg_mode == BACKGROUND_FULL_TRACE_LINEAR:
            bg_slope, bg_intercept = cls._estimate_symmetric_linear_background(
                x_arr,
                y_arr,
                centers=None,
                widths=None,
                fit_range=None,
                peak_profile=profile,
                symmetry_hint_range=fit_range,
                intercept_hint_range=fit_range,
            )
            y_seed = np.asarray(
                y_arr - cls._background_model(x_arr, offset=bg_intercept, bg_slope=bg_slope),
                dtype=float,
            )
            rough_centers = cls.get_row_initial_guess(
                y=y_seed,
                x=x_arr,
                n_peaks=n_peaks,
                search_range=fit_range,
                fill_to_count=True,
                min_count=1,
            )
            rough_centers = cls._clean_centers(rough_centers, fit_range, max_count=int(max(1, n_peaks)))
            rough_widths = cls._seed_widths_from_centers(
                rough_centers,
                fit_range,
                point_count=x_arr.size,
                fixed_sigma=fixed_sigma,
            )
            bg_slope, bg_intercept = cls._estimate_symmetric_linear_background(
                x_arr,
                y_arr,
                centers=rough_centers,
                widths=rough_widths,
                fit_range=None,
                peak_profile=profile,
                symmetry_hint_range=fit_range,
                intercept_hint_range=fit_range,
            )
            y_seed = np.asarray(
                y_arr - cls._background_model(x_arr, offset=bg_intercept, bg_slope=bg_slope),
                dtype=float,
            )
        centers = cls.get_row_initial_guess(
            y=y_seed,
            x=x_arr,
            n_peaks=n_peaks,
            search_range=fit_range,
            fill_to_count=True,
            min_count=1,
        )
        centers = cls._clean_centers(centers, fit_range, max_count=int(max(1, n_peaks)))
        return np.asarray(x_arr, dtype=float), np.asarray(y_seed, dtype=float), np.asarray(centers, dtype=float), float(bg_slope), float(bg_intercept)

    @classmethod
    def get_row_initial_guess(cls, y, x, n_peaks, search_range, fill_to_count=True, min_count=1):
        x = np.asarray(x, dtype=float).ravel()
        y = np.asarray(y, dtype=float).ravel()
        fit_min = float(min(search_range))
        fit_max = float(max(search_range))
        if fit_max <= fit_min:
            fit_max = fit_min + 1e-6
        fallback = np.linspace(fit_min, fit_max, int(max(1, n_peaks)), dtype=float)

        def _fallback(count):
            count = int(max(1, count))
            if count == 1:
                return np.asarray([0.5 * (fit_min + fit_max)], dtype=float)
            return np.linspace(fit_min, fit_max, count, dtype=float)

        finite = np.isfinite(x) & np.isfinite(y)
        mask = finite & (x >= fit_min) & (x <= fit_max)
        if np.count_nonzero(mask) < 4:
            keep = int(max(1, n_peaks if fill_to_count else min_count))
            return _fallback(keep)

        xs = x[mask]
        ys = y[mask]
        order = np.argsort(xs)
        xs = np.asarray(xs[order], dtype=float)
        ys = np.asarray(ys[order], dtype=float)
        if xs.size < 4:
            keep = int(max(1, n_peaks if fill_to_count else min_count))
            return _fallback(keep)
        dx_est = float(np.nanmedian(np.abs(np.diff(xs)))) if xs.size > 1 else max(1e-6, (fit_max - fit_min) / 200.0)
        if not np.isfinite(dx_est) or dx_est <= 0:
            dx_est = max(1e-6, (fit_max - fit_min) / 200.0)
        edge_margin = max(4.0 * dx_est, 0.025 * (fit_max - fit_min))

        ys_despiked = cls._despike_signal(ys)
        ys_s = np.asarray(ys_despiked, dtype=float)
        if HAS_MULTIPEAK_BACKEND and xs.size >= 7:
            win = min(xs.size if xs.size % 2 == 1 else xs.size - 1, 11)
            win = max(5, win)
            if win % 2 == 0:
                win -= 1
            if win >= 5 and win <= xs.size:
                try:
                    ys_s = savgol_filter(ys_despiked, window_length=win, polyorder=min(3, win - 2))
                except Exception:
                    ys_s = np.asarray(ys_despiked, dtype=float)

        try:
            span = float(np.nanpercentile(ys_s, 95) - np.nanpercentile(ys_s, 5))
        except Exception:
            span = float(np.nanmax(ys_s) - np.nanmin(ys_s))
        span = max(span, 1e-8)
        noise = max(cls._robust_noise(ys_s), 1e-8)
        prom = max(0.02 * span, 1.0 * noise, 1e-8)
        # Allow closer neighboring peaks in one STS; coarse spacing was swallowing
        # genuine nearby peaks and leaving broad shoulders behind.
        distance = max(1, int(np.ceil(xs.size / max(6, 3 * int(max(1, n_peaks))))))
        min_width_pts = max(1.25, min(5.0, 0.30 * max(1, distance) + 0.9))

        peaks_idx = np.array([], dtype=int)
        prominences = np.array([], dtype=float)
        peaks_hp_idx = np.array([], dtype=int)
        prominences_hp = np.array([], dtype=float)
        peaks_local_idx = np.array([], dtype=int)
        prominences_local = np.array([], dtype=float)
        resid = np.asarray(ys_s, dtype=float)
        resid_local = np.asarray(ys_s, dtype=float)
        if HAS_MULTIPEAK_BACKEND:
            try:
                peaks_idx, props = find_peaks(
                    ys_s,
                    prominence=prom,
                    distance=distance,
                    width=min_width_pts,
                )
                prominences = np.asarray(props.get("prominences", np.zeros(peaks_idx.size)), dtype=float)
            except Exception:
                peaks_idx = np.array([], dtype=int)
                prominences = np.array([], dtype=float)
            try:
                bg_win = max(9, int(round(xs.size * 0.35)))
                max_odd = xs.size if xs.size % 2 == 1 else xs.size - 1
                bg_win = min(bg_win, max_odd)
                if bg_win % 2 == 0:
                    bg_win -= 1
                if bg_win >= 7:
                    baseline = savgol_filter(ys_s, window_length=bg_win, polyorder=min(3, bg_win - 2))
                else:
                    baseline = ys_s
                resid = np.asarray(ys_s - baseline, dtype=float)
                resid_noise = max(cls._robust_noise(resid), 1e-8)
                try:
                    resid_span = float(np.nanpercentile(resid, 95) - np.nanpercentile(resid, 5))
                except Exception:
                    resid_span = float(np.nanmax(resid) - np.nanmin(resid))
                resid_span = max(resid_span, 1e-8)
                prom_hp = max(0.75 * resid_noise, 0.012 * span, 0.18 * resid_span, 1e-8)
                peaks_hp_idx, props_hp = find_peaks(
                    resid,
                    prominence=prom_hp,
                    distance=max(1, distance // 2),
                    width=max(1.0, 0.75 * min_width_pts),
                )
                prominences_hp = np.asarray(props_hp.get("prominences", np.zeros(peaks_hp_idx.size)), dtype=float)
            except Exception:
                peaks_hp_idx = np.array([], dtype=int)
                prominences_hp = np.array([], dtype=float)
                resid = np.asarray(ys_s, dtype=float)
            try:
                local_win = max(7, int(round(xs.size * 0.18)))
                max_odd = xs.size if xs.size % 2 == 1 else xs.size - 1
                local_win = min(local_win, max_odd)
                if local_win % 2 == 0:
                    local_win -= 1
                if local_win >= 7:
                    baseline_local = savgol_filter(ys_s, window_length=local_win, polyorder=min(3, local_win - 2))
                else:
                    baseline_local = ys_s
                resid_local = np.asarray(ys_s - baseline_local, dtype=float)
                local_noise = max(cls._robust_noise(resid_local), 1e-8)
                try:
                    resid_local_span = float(np.nanpercentile(resid_local, 95) - np.nanpercentile(resid_local, 5))
                except Exception:
                    resid_local_span = float(np.nanmax(resid_local) - np.nanmin(resid_local))
                resid_local_span = max(resid_local_span, 1e-8)
                prom_local = max(0.60 * local_noise, 0.004 * span, 0.14 * resid_local_span, 1e-8)
                peaks_local_idx, props_local = find_peaks(
                    resid_local,
                    prominence=prom_local,
                    distance=max(1, distance // 3),
                    width=max(1.0, 0.65 * min_width_pts),
                )
                prominences_local = np.asarray(
                    props_local.get("prominences", np.zeros(peaks_local_idx.size)),
                    dtype=float,
                )
            except Exception:
                peaks_local_idx = np.array([], dtype=int)
                prominences_local = np.array([], dtype=float)
                resid_local = np.asarray(ys_s, dtype=float)

        candidate_scores = {}

        def _snap_indices_to_local_maxima(indices, radius):
            idx_arr = np.asarray(indices, dtype=int).ravel()
            if idx_arr.size == 0:
                return np.zeros(0, dtype=int)
            radius = int(max(1, radius))
            out = []
            for idx_i in idx_arr:
                idx_i = int(np.clip(int(idx_i), 0, xs.size - 1))
                lo = max(0, idx_i - radius)
                hi = min(xs.size, idx_i + radius + 1)
                yy = ys_s[lo:hi]
                if yy.size == 0:
                    out.append(idx_i)
                    continue
                out.append(int(lo + int(np.argmax(yy))))
            return np.asarray(out, dtype=int)

        local_radius = max(3, int(np.ceil(1.25 * distance)))
        resid_scale = max(float(np.nanmax(np.abs(resid))) if resid.size else 0.0, 1e-8)
        resid_noise = max(cls._robust_noise(resid), 1e-8)
        resid_local_scale = max(float(np.nanmax(np.abs(resid_local))) if resid_local.size else 0.0, 1e-8)
        resid_local_noise = max(cls._robust_noise(resid_local), 1e-8)

        def _peak_shape_metrics(signal, idx_i):
            sig = np.asarray(signal, dtype=float)
            if sig.size == 0:
                return 0.0, 0.0, 0.0, 0.0
            idx_i = int(np.clip(int(idx_i), 0, sig.size - 1))
            lo = max(0, idx_i - local_radius)
            hi = min(sig.size, idx_i + local_radius + 1)
            peak_y = float(sig[idx_i])
            left_slice = sig[lo:idx_i + 1]
            right_slice = sig[idx_i:hi]
            if left_slice.size == 0 or right_slice.size == 0:
                return 0.0, 0.0, 0.0, 0.0

            left_min = float(np.nanmin(left_slice))
            right_min = float(np.nanmin(right_slice))
            left_drop = max(0.0, peak_y - left_min)
            right_drop = max(0.0, peak_y - right_min)
            two_side_drop = min(left_drop, right_drop)
            balance = two_side_drop / max(max(left_drop, right_drop), 1e-8)

            half_level = peak_y - 0.5 * two_side_drop
            left = idx_i
            while left > lo and float(sig[left - 1]) > half_level:
                left -= 1
            right = idx_i
            while right + 1 < hi and float(sig[right + 1]) > half_level:
                right += 1
            width = float(xs[right] - xs[left]) if right > left else dx_est
            width_pref = max(6.0 * dx_est, 0.10 * (fit_max - fit_min) / max(1, n_peaks))
            narrowness = float(np.clip(width_pref / max(width_pref + max(width, 0.0), 1e-8), 0.0, 1.0))

            if 0 < idx_i < sig.size - 1:
                shoulder_y = 0.5 * (float(sig[idx_i - 1]) + float(sig[idx_i + 1]))
                sharp_drop = max(0.0, peak_y - shoulder_y)
                sharpness = float(np.clip(sharp_drop / max(two_side_drop, 1e-8), 0.0, 1.0))
            else:
                sharpness = 0.0
            return two_side_drop, balance, narrowness, sharpness

        def _candidate_peak_shape_score(idx_i):
            raw_drop, raw_balance, raw_narrow, raw_sharp = _peak_shape_metrics(ys_s, idx_i)
            hp_drop, hp_balance, hp_narrow, hp_sharp = _peak_shape_metrics(resid, idx_i)
            local_drop, local_balance, local_narrow, local_sharp = _peak_shape_metrics(resid_local, idx_i)
            raw_norm = raw_drop / max(span, 1e-8)
            hp_norm = hp_drop / resid_scale
            local_norm = local_drop / resid_local_scale
            two_side_strength = max(raw_norm, 0.9 * hp_norm, 1.05 * local_norm)
            balance = max(raw_balance, 0.75 * hp_balance, 0.80 * local_balance)
            narrowness = max(raw_narrow, hp_narrow, local_narrow)
            sharpness = max(raw_sharp, 0.8 * hp_sharp, local_sharp)
            is_distinct = (
                raw_drop >= max(0.9 * noise, 0.012 * span, 1e-8)
                or hp_drop >= max(1.0 * resid_noise, 0.08 * resid_scale, 1e-8)
                or local_drop >= max(0.9 * resid_local_noise, 0.06 * resid_local_scale, 1e-8)
            )
            shape_gain = (
                (0.20 + 0.80 * balance)
                * (0.25 + 0.75 * narrowness)
                * (0.20 + 0.80 * sharpness)
            )
            return is_distinct, two_side_strength, balance, shape_gain

        def _add_candidates(indices, scores):
            for idx_i, score in zip(np.asarray(indices, dtype=int), np.asarray(scores, dtype=float)):
                if idx_i < 0 or idx_i >= xs.size or (not np.isfinite(score)):
                    continue
                x_i = float(xs[int(idx_i)])
                if x_i <= fit_min + edge_margin or x_i >= fit_max - edge_margin:
                    continue
                is_distinct, two_side_strength, balance, shape_gain = _candidate_peak_shape_score(int(idx_i))
                if not is_distinct:
                    continue
                if balance < 0.16 and two_side_strength < 0.10:
                    continue
                weighted = (0.45 * float(score) + 1.85 * two_side_strength) * shape_gain
                candidate_scores[int(idx_i)] = max(float(weighted), candidate_scores.get(int(idx_i), -np.inf))

        def _add_loose_peak_candidates():
            loose_raw = np.array([], dtype=int)
            loose_hp = np.array([], dtype=int)
            loose_local = np.array([], dtype=int)
            if HAS_MULTIPEAK_BACKEND:
                try:
                    loose_prom = max(0.35 * prom, 0.5 * noise, 1e-8)
                    loose_raw, _ = find_peaks(
                        ys_s,
                        prominence=loose_prom,
                        distance=max(1, distance // 2),
                        width=max(1.0, 0.60 * min_width_pts),
                    )
                except Exception:
                    loose_raw = np.array([], dtype=int)
                try:
                    hp_noise = max(cls._robust_noise(resid), 1e-8)
                    loose_hp_prom = max(0.45 * hp_noise, 0.006 * span, 1e-8)
                    loose_hp, _ = find_peaks(
                        resid,
                        prominence=loose_hp_prom,
                        distance=max(1, distance // 3),
                        width=max(1.0, 0.55 * min_width_pts),
                    )
                except Exception:
                    loose_hp = np.array([], dtype=int)
                try:
                    local_noise = max(cls._robust_noise(resid_local), 1e-8)
                    loose_local_prom = max(0.40 * local_noise, 0.003 * span, 1e-8)
                    loose_local, _ = find_peaks(
                        resid_local,
                        prominence=loose_local_prom,
                        distance=max(1, distance // 4),
                        width=max(1.0, 0.50 * min_width_pts),
                    )
                except Exception:
                    loose_local = np.array([], dtype=int)

            if loose_raw.size == 0 and ys_s.size >= 3:
                loose_raw = np.where((ys_s[1:-1] >= ys_s[:-2]) & (ys_s[1:-1] >= ys_s[2:]))[0] + 1
            if loose_hp.size == 0 and resid.size >= 3:
                loose_hp = np.where((resid[1:-1] >= resid[:-2]) & (resid[1:-1] >= resid[2:]))[0] + 1
            if loose_local.size == 0 and resid_local.size >= 3:
                loose_local = np.where((resid_local[1:-1] >= resid_local[:-2]) & (resid_local[1:-1] >= resid_local[2:]))[0] + 1

            if loose_raw.size:
                loose_raw = _snap_indices_to_local_maxima(loose_raw, max(1, distance // 2))
                raw_score = np.clip((ys_s[loose_raw] - np.nanmedian(ys_s)) / max(span, 1e-8), 0.0, None)
                _add_candidates(loose_raw, raw_score + 0.25)
            if loose_hp.size:
                loose_hp = _snap_indices_to_local_maxima(loose_hp, max(1, distance // 2))
                hp_scale = max(np.nanmax(np.abs(resid)), 1e-8)
                hp_score = np.clip(resid[loose_hp] / hp_scale, 0.0, None)
                _add_candidates(loose_hp, hp_score + 0.15)
            if loose_local.size:
                local_scale = max(np.nanmax(np.abs(resid_local)), 1e-8)
                local_score = np.clip(resid_local[np.asarray(loose_local, dtype=int)] / local_scale, 0.0, None)
                _add_candidates(loose_local, local_score + 0.18)

        if peaks_idx.size:
            raw_scale = max(prom, noise, 1e-8)
            raw_scores = (prominences / raw_scale) + np.clip((ys_s[peaks_idx] - np.nanmedian(ys_s)) / span, 0.0, None)
            _add_candidates(peaks_idx, raw_scores)
        if peaks_hp_idx.size:
            hp_scale = max(cls._robust_noise(resid), 1e-8)
            hp_scores = 1.25 * (prominences_hp / hp_scale) + np.clip(resid[peaks_hp_idx] / max(np.nanmax(np.abs(resid)), 1e-8), 0.0, None)
            _add_candidates(peaks_hp_idx, hp_scores)
        if peaks_local_idx.size:
            local_scale = max(cls._robust_noise(resid_local), 1e-8)
            local_scores = (
                1.45 * (prominences_local / local_scale)
                + np.clip(resid_local[peaks_local_idx] / max(np.nanmax(np.abs(resid_local)), 1e-8), 0.0, None)
            )
            _add_candidates(peaks_local_idx, local_scores)
        _add_loose_peak_candidates()
        if not candidate_scores:
            top_k = int(max(1, n_peaks if fill_to_count else min_count))
            top_idx = np.argsort(ys_s)[-top_k:]
            top_idx = _snap_indices_to_local_maxima(top_idx, max(1, distance // 2))
            _add_candidates(top_idx, ys_s[top_idx])

        ranked = sorted(candidate_scores.items(), key=lambda kv: kv[1], reverse=True)
        chosen_idx = []
        sep_eps = max(2.5 * dx_est, 0.008 * (fit_max - fit_min))
        for idx_i, _score in ranked:
            x_i = float(xs[int(idx_i)])
            if all(abs(x_i - float(xs[j])) > sep_eps for j in chosen_idx):
                chosen_idx.append(int(idx_i))
            if len(chosen_idx) >= int(max(1, n_peaks)):
                break
        if fill_to_count and len(chosen_idx) < int(max(1, n_peaks)):
            loose_rank = np.argsort(ys_s)[::-1]
            loose_rank = _snap_indices_to_local_maxima(loose_rank, max(1, distance // 2))
            for idx_i in loose_rank:
                x_i = float(xs[int(idx_i)])
                if all(abs(x_i - float(xs[j])) > sep_eps for j in chosen_idx):
                    chosen_idx.append(int(idx_i))
                if len(chosen_idx) >= int(max(1, n_peaks)):
                    break
        if not chosen_idx:
            interior = np.where((xs > fit_min + edge_margin) & (xs < fit_max - edge_margin))[0]
            if interior.size > 0:
                chosen_idx = [int(interior[int(np.argmax(ys_s[interior]))])]
            else:
                chosen_idx = [int(np.argmax(ys_s))]

        chosen_idx = _snap_indices_to_local_maxima(np.asarray(chosen_idx, dtype=int), max(2, distance))
        seeds = cls._clean_centers(
            np.asarray(xs[np.asarray(chosen_idx, dtype=int)], dtype=float),
            (fit_min, fit_max),
            max_count=int(max(1, n_peaks)),
        )
        if fill_to_count and seeds.size < int(max(1, n_peaks)):
            loose_rank = np.argsort(ys_s)[::-1]
            loose_rank = _snap_indices_to_local_maxima(loose_rank, max(1, distance // 2))
            extra = []
            for idx_i in loose_rank:
                x_i = float(xs[int(idx_i)])
                if all(abs(x_i - float(s)) > sep_eps for s in seeds) and all(abs(x_i - float(s)) > sep_eps for s in extra):
                    extra.append(x_i)
                if seeds.size + len(extra) >= int(max(1, n_peaks)):
                    break
            if extra:
                seeds = cls._clean_centers(
                    np.concatenate([np.asarray(seeds, dtype=float), np.asarray(extra, dtype=float)]),
                    (fit_min, fit_max),
                    max_count=int(max(1, n_peaks)),
                )
        if not fill_to_count:
            if seeds.size == 0:
                need = int(max(1, min_count))
                return _fallback(need)
            return seeds
        if seeds.size >= int(max(1, n_peaks)):
            return np.asarray(seeds[:int(max(1, n_peaks))], dtype=float)
        return cls._merge_initial_centers(seeds, fallback, n_peaks, (fit_min, fit_max))

    @staticmethod
    def _clean_centers(values, fit_range, max_count=None):
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        if fit_max <= fit_min:
            fit_max = fit_min + 1e-6
        arr = np.asarray(values, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return np.zeros(0, dtype=float)
        arr = np.clip(arr, fit_min, fit_max)
        arr = np.sort(arr)
        eps = max(1e-6, 1e-3 * (fit_max - fit_min))
        out = []
        for val in arr:
            if not out or abs(float(val) - float(out[-1])) > eps:
                out.append(float(val))
        arr = np.asarray(out, dtype=float)
        if max_count is not None and arr.size > int(max_count):
            arr = arr[:int(max_count)]
        return arr

    @staticmethod
    def _merge_initial_centers(seed_centers, fallback_centers, n_peaks, fit_range):
        n_peaks = int(max(1, n_peaks))
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        if fit_max <= fit_min:
            fit_max = fit_min + 1e-6
        eps = max(1e-6, 1e-3 * (fit_max - fit_min))

        def _clean(values):
            arr = np.asarray(values, dtype=float).ravel()
            arr = arr[np.isfinite(arr)]
            if arr.size == 0:
                return np.zeros(0, dtype=float)
            arr = np.clip(arr, fit_min, fit_max)
            arr = np.sort(arr)
            out = []
            for val in arr:
                if not out or abs(val - out[-1]) > eps:
                    out.append(float(val))
            return np.asarray(out, dtype=float)

        seeds = _clean(seed_centers)
        fallback = _clean(fallback_centers)
        if fallback.size == 0:
            fallback = np.linspace(fit_min, fit_max, n_peaks, dtype=float)

        merged = []
        for val in seeds:
            if len(merged) >= n_peaks:
                break
            merged.append(float(val))

        for val in fallback:
            if len(merged) >= n_peaks:
                break
            if not merged or float(np.min(np.abs(np.asarray(merged, dtype=float) - val))) > eps:
                merged.append(float(val))

        while len(merged) < n_peaks:
            fill = np.linspace(fit_min, fit_max, n_peaks, dtype=float)
            next_idx = min(len(merged), fill.size - 1)
            merged.append(float(fill[next_idx]))

        return np.sort(np.asarray(merged[:n_peaks], dtype=float))

    @staticmethod
    def _safe_r2(y_true, y_pred):
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        if y_true.size == 0:
            return -np.inf
        den = np.var(y_true) * y_true.size
        if den <= 1e-20:
            return -np.inf
        return 1.0 - float(np.sum((y_true - y_pred) ** 2) / den)

    @staticmethod
    def _robust_noise(y):
        vals = np.asarray(y, dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size < 4:
            return 1e-8
        med = float(np.nanmedian(vals))
        mad = float(np.nanmedian(np.abs(vals - med)))
        sigma_mad = 1.4826 * mad
        sigma_std = float(np.nanstd(vals))
        sigma = sigma_mad if np.isfinite(sigma_mad) and sigma_mad > 1e-12 else sigma_std
        if not np.isfinite(sigma) or sigma <= 1e-12:
            sigma = sigma_std
        if not np.isfinite(sigma) or sigma <= 1e-12:
            sigma = 1e-8
        return float(sigma)

    def _annotate_peak_validity(
        self,
        res,
        y_fit,
        bias_fit,
        fit_range,
        peak_snr_min=2.0,
        peak_amp_frac_min=0.03,
    ):
        if res is None:
            return None
        n_peaks = int(res.amps.size)
        if n_peaks <= 0:
            res.peak_valid = np.zeros(0, dtype=bool)
            res.peak_snr = np.zeros(0, dtype=float)
            res.amp_threshold = np.nan
            return res
        if not bool(getattr(res, "success", False)):
            res.peak_valid = np.zeros(n_peaks, dtype=bool)
            res.peak_snr = np.zeros(n_peaks, dtype=float)
            res.amp_threshold = np.nan
            return res

        y_fit = np.asarray(y_fit, dtype=float)
        bias_fit = np.asarray(bias_fit, dtype=float)
        amps = np.asarray(res.amps, dtype=float)
        centers = np.asarray(res.centers, dtype=float)
        sigmas = np.asarray(res.sigmas, dtype=float)
        valid_num = np.isfinite(y_fit) & np.isfinite(bias_fit)
        y_loc = y_fit[valid_num]
        x_loc = bias_fit[valid_num]

        if y_loc.size < 4:
            res.peak_valid = np.zeros(n_peaks, dtype=bool)
            res.peak_snr = np.zeros(n_peaks, dtype=float)
            res.amp_threshold = np.nan
            return res

        y_model = self._sum_model(
            x_loc,
            amps,
            centers,
            sigmas,
            offset=getattr(res, "offset", 0.0),
            bg_slope=getattr(res, "bg_slope", 0.0),
            bg_poly_coeffs=getattr(res, "bg_poly_coeffs", None),
            bg_x_center=getattr(res, "bg_x_center", 0.0),
            bg_x_scale=getattr(res, "bg_x_scale", 1.0),
            peak_profile=getattr(res, "peak_profile", GAUSSIAN_PROFILE),
        )
        resid = y_loc - y_model
        noise = self._robust_noise(resid)
        try:
            span = float(np.nanpercentile(y_loc, 95) - np.nanpercentile(y_loc, 5))
        except Exception:
            span = float(np.nanmax(y_loc) - np.nanmin(y_loc))
        if not np.isfinite(span) or span <= 0:
            span = float(np.nanmax(np.abs(y_loc))) if y_loc.size else 0.0
        span = max(span, 1e-8)

        peak_snr_min = max(0.0, float(peak_snr_min))
        peak_amp_frac_min = max(0.0, float(peak_amp_frac_min))
        amp_thr = max(peak_snr_min * noise, peak_amp_frac_min * span, 1e-8)

        if x_loc.size > 1:
            dx = float(np.nanmedian(np.abs(np.diff(np.sort(x_loc)))))
            if not np.isfinite(dx) or dx <= 0:
                dx = 0.0
        else:
            dx = 0.0
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        edge_margin = max(dx, 0.01 * max(1e-8, fit_max - fit_min))
        sigma_min = max(1e-8, 0.35 * max(dx, 1e-6))
        sigma_max = 0.75 * max(1e-8, fit_max - fit_min)

        snr = amps / max(noise, 1e-8)
        valid = (
            np.isfinite(amps)
            & np.isfinite(centers)
            & np.isfinite(sigmas)
            & (amps >= amp_thr)
            & (sigmas >= sigma_min)
            & (sigmas <= sigma_max)
            & (centers > fit_min + edge_margin)
            & (centers < fit_max - edge_margin)
        )
        res.peak_valid = np.asarray(valid, dtype=bool)
        res.peak_snr = np.asarray(snr, dtype=float)
        res.amp_threshold = float(amp_thr)
        return res

    @staticmethod
    def _is_good_fit(res, threshold):
        if res is None:
            return False
        if not res.success:
            return False
        if not np.isfinite(res.r2):
            return False
        return res.r2 >= float(threshold)

    def _residual_peak_candidates(self, y_fit, bias_fit, fit_range, current_centers, model_y, max_count=3):
        y_fit = np.asarray(y_fit, dtype=float)
        bias_fit = np.asarray(bias_fit, dtype=float)
        model_y = np.asarray(model_y, dtype=float)
        if y_fit.size < 4 or bias_fit.size != y_fit.size or model_y.size != y_fit.size:
            return np.zeros(0, dtype=float)
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        span = max(1e-6, fit_max - fit_min)
        current = self._clean_centers(current_centers, fit_range, max_count=None)
        resid_pos = np.clip(y_fit - model_y, 0.0, None)
        if resid_pos.size < 4:
            return np.zeros(0, dtype=float)
        resid_noise = max(self._robust_noise(resid_pos), 1e-8)
        try:
            resid_span = float(np.nanpercentile(resid_pos, 95) - np.nanpercentile(resid_pos, 5))
        except Exception:
            resid_span = float(np.nanmax(resid_pos) - np.nanmin(resid_pos))
        resid_span = max(resid_span, 0.0)
        if resid_span < max(2.5 * resid_noise, 0.01 * max(1e-8, np.nanmax(np.abs(y_fit)))):
            return np.zeros(0, dtype=float)

        cand = self.get_row_initial_guess(
            y=resid_pos,
            x=bias_fit,
            n_peaks=int(max(1, max_count)),
            search_range=(fit_min, fit_max),
            fill_to_count=False,
            min_count=1,
        )
        cand = self._clean_centers(cand, (fit_min, fit_max), max_count=int(max(1, max_count)))
        if cand.size == 0:
            return np.zeros(0, dtype=float)

        if bias_fit.size > 1:
            dx = float(np.nanmedian(np.abs(np.diff(np.sort(bias_fit)))))
            if not np.isfinite(dx) or dx <= 0:
                dx = 0.0
        else:
            dx = 0.0
        sep = max(3.0 * dx, 0.015 * span)
        out = []
        for c in np.asarray(cand, dtype=float):
            if current.size and np.min(np.abs(current - float(c))) <= sep:
                continue
            if out and np.min(np.abs(np.asarray(out, dtype=float) - float(c))) <= sep:
                continue
            out.append(float(c))
        return np.asarray(out, dtype=float)

    def _replacement_order(self, res, protected_centers=None, fit_range=None):
        if res is None:
            return np.zeros(0, dtype=int)
        centers = np.asarray(getattr(res, "centers", np.zeros(0, dtype=float)), dtype=float)
        amps = np.asarray(getattr(res, "amps", np.zeros(0, dtype=float)), dtype=float)
        n = int(min(centers.size, amps.size))
        if n <= 0:
            return np.zeros(0, dtype=int)
        peak_valid = getattr(res, "peak_valid", None)
        if not isinstance(peak_valid, np.ndarray) or peak_valid.size != n:
            peak_valid = np.ones(n, dtype=bool)
        protected = self._clean_centers(protected_centers, fit_range, max_count=None) if fit_range is not None else np.zeros(0, dtype=float)
        span = max(1e-6, float(max(fit_range)) - float(min(fit_range))) if fit_range is not None else 1.0
        protect_sep = 0.01 * span
        replaceable = []
        protected_idx = []
        amp_rank = np.where(np.isfinite(amps[:n]), amps[:n], np.inf)
        for idx in range(n):
            is_protected = protected.size > 0 and np.min(np.abs(protected - float(centers[idx]))) <= protect_sep
            score = (1 if bool(peak_valid[idx]) else 0, float(amp_rank[idx]), idx)
            if is_protected:
                protected_idx.append(score)
            else:
                replaceable.append(score)
        ordered = replaceable + protected_idx
        if not ordered:
            return np.arange(n, dtype=int)
        ordered.sort(key=lambda item: (item[0], item[1], item[2]))
        return np.asarray([int(item[2]) for item in ordered], dtype=int)

    def _fit_single_position(
        self,
        y_fit,
        bias_fit,
        n_peaks,
        fit_range,
        init_centers,
        fixed_sigma=None,
        peak_profile=GAUSSIAN_PROFILE,
        background_mode=BACKGROUND_OFFSET,
        full_bias=None,
        full_row=None,
    ):
        peak_profile = _normalize_peak_profile(peak_profile)
        background_mode = _normalize_background_mode(background_mode)
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        fix_linear_bg = background_mode == BACKGROUND_FULL_TRACE_LINEAR
        fit_cubic_bg = background_mode == BACKGROUND_IGOR_CUBIC
        y_fit = np.asarray(y_fit, dtype=float)
        bias_fit = np.asarray(bias_fit, dtype=float)
        finite = np.isfinite(y_fit) & np.isfinite(bias_fit)
        y_fit = y_fit[finite]
        bias_fit = bias_fit[finite]
        if y_fit.size != bias_fit.size or y_fit.size < max(8, n_peaks * 3):
            return PeakFitResult(
                amps=np.full(n_peaks, np.nan),
                centers=np.full(n_peaks, np.nan),
                sigmas=np.full(n_peaks, np.nan),
                offset=np.nan,
                bg_slope=np.nan,
                chi2=np.inf,
                r2=-np.inf,
                success=False,
                message="Not enough points in fit range.",
                peak_profile=peak_profile,
                background_mode=background_mode,
                fit_min=fit_min,
                fit_max=fit_max,
            )
        span = max(1e-6, fit_max - fit_min)
        min_sigma = max(1e-4, span / max(1200.0, 25.0 * bias_fit.size))
        min_sep = max(1e-4, span / 250.0)
        sigma_seed_cap = max(min_sigma * 2.0, 0.25 * span)
        centers0 = self._merge_initial_centers(init_centers, np.linspace(fit_min, fit_max, n_peaks), n_peaks, (fit_min, fit_max))
        width_seed0 = np.zeros(n_peaks, dtype=float)
        for i in range(n_peaks):
            dl = centers0[i] - centers0[i - 1] if i > 0 else np.inf
            dr = centers0[i + 1] - centers0[i] if i < n_peaks - 1 else np.inf
            spacing = min(dl, dr)
            if not np.isfinite(spacing):
                spacing = span / max(2.0, n_peaks)
            width_seed0[i] = np.clip(0.2 * spacing, min_sigma, sigma_seed_cap)
        if fixed_sigma is not None and np.isfinite(fixed_sigma):
            width_seed0[:] = np.clip(float(fixed_sigma), min_sigma, sigma_seed_cap)
        y_lo = float(np.nanpercentile(y_fit, 10)) if y_fit.size else 0.0
        y_hi = float(np.nanpercentile(y_fit, 99.5)) if y_fit.size else 0.0
        y_min = float(np.nanmin(y_fit)) if y_fit.size else 0.0
        y_max = float(np.nanmax(y_fit)) if y_fit.size else 0.0
        y_span = max(1e-8, y_max - y_min)
        bg_slope0 = 0.0
        bg_poly0 = None
        bg_x_center0 = np.nan
        bg_x_scale0 = np.nan
        if background_mode == BACKGROUND_FULL_TRACE_LINEAR:
            bg_src_x = np.asarray(full_bias if full_bias is not None else bias_fit, dtype=float)
            bg_src_y = np.asarray(full_row if full_row is not None else y_fit, dtype=float)
            bg_slope0, offset0 = self._estimate_symmetric_linear_background(
                bg_src_x,
                bg_src_y,
                centers=centers0,
                widths=width_seed0,
                fit_range=None,
                peak_profile=peak_profile,
                symmetry_hint_range=(fit_min, fit_max),
                intercept_hint_range=(fit_min, fit_max),
            )
        elif fit_cubic_bg:
            bg_poly0, bg_x_center0, bg_x_scale0 = self._estimate_peak_masked_cubic_background(
                bias_fit,
                y_fit,
                centers=centers0,
                widths=width_seed0,
                fit_range=(fit_min, fit_max),
                peak_profile=peak_profile,
            )
            bg_slope0, offset0 = self._legacy_linear_from_cubic(
                bg_poly0,
                bg_x_center=bg_x_center0,
                bg_x_scale=bg_x_scale0,
            )
        else:
            offset0 = y_lo
        offset0 = float(np.clip(offset0, y_min - 0.25 * y_span, y_max + 0.25 * y_span))
        bg_seed = self._background_model(
            bias_fit,
            offset=offset0,
            bg_slope=bg_slope0,
            bg_poly_coeffs=bg_poly0,
            bg_x_center=bg_x_center0,
            bg_x_scale=bg_x_scale0,
        )
        amps0 = np.zeros(n_peaks, dtype=float)
        sig0 = np.asarray(width_seed0, dtype=float).copy()
        for i, c in enumerate(centers0):
            idx = int(np.argmin(np.abs(bias_fit - c)))
            amps0[i] = max(float(y_fit[idx] - bg_seed[idx]), 1e-6)

        y_abs = float(np.nanmax(np.abs(y_fit))) if y_fit.size else 0.0
        amp_ref = max(1e-4, y_hi - float(np.nanmedian(bg_seed)), 0.35 * y_abs, 0.2 * y_span)
        amp_max = max(1e-4, amp_ref * 3.0)
        offset_pad = max(1e-4, 0.5 * y_span)
        offset_lb = y_min - offset_pad
        offset_ub = y_max + offset_pad
        lb = []
        ub = []
        x0 = []
        centers0 = np.asarray(centers0, dtype=float)

        for i in range(n_peaks):
            a0 = float(np.clip(amps0[i], 1e-8, amp_max))
            lb.append(0.0)
            ub.append(amp_max)
            x0.append(a0)

        for i in range(n_peaks):
            c0 = float(np.clip(centers0[i], fit_min, fit_max))
            cmin = fit_min
            cmax = fit_max
            if cmax <= cmin:
                mid = float(np.clip(c0, fit_min, fit_max))
                cmin = max(fit_min, mid - min_sep)
                cmax = min(fit_max, mid + min_sep)
                if cmax <= cmin:
                    cmax = cmin + max(min_sep, 1e-5)
            c0 = float(np.clip(c0, cmin, cmax))
            lb.append(cmin)
            ub.append(cmax)
            x0.append(c0)

        fit_sigma = None
        if fixed_sigma is not None:
            fit_sigma = float(np.clip(abs(float(fixed_sigma)), min_sigma, max(min_sigma * 1.1, 0.5 * span)))
        else:
            centers_sorted = np.sort(centers0)
            for i in range(n_peaks):
                dl = centers_sorted[i] - centers_sorted[i - 1] if i > 0 else np.inf
                dr = centers_sorted[i + 1] - centers_sorted[i] if i < n_peaks - 1 else np.inf
                spacing = min(dl, dr)
                if not np.isfinite(spacing):
                    spacing = span / max(2.0, n_peaks)
                smax = min(max(min_sigma * 1.5, 0.45 * spacing), 0.5 * span)
                s0 = float(np.clip(abs(sig0[i]), min_sigma, smax))
                lb.append(min_sigma)
                ub.append(smax)
                x0.append(s0)

        if fit_cubic_bg:
            bg_poly0 = np.asarray(bg_poly0 if bg_poly0 is not None else [offset0, 0.0, 0.0, 0.0], dtype=float).ravel()
            if bg_poly0.size < 4:
                bg_poly0 = np.pad(bg_poly0, (0, 4 - bg_poly0.size), mode="constant")
            bg_coef_ref = max(
                1e-4,
                y_span,
                float(np.nanmax(np.abs(y_fit))) if y_fit.size else 0.0,
                float(np.nanmax(np.abs(bg_poly0[:4]))) if np.any(np.isfinite(bg_poly0[:4])) else 0.0,
            )
            bg_coef_bound = max(1e-3, 20.0 * bg_coef_ref)
            for j in range(4):
                c0 = float(np.clip(bg_poly0[j], -bg_coef_bound, bg_coef_bound))
                x0.append(c0)
                lb.append(-bg_coef_bound)
                ub.append(bg_coef_bound)
        elif not fix_linear_bg:
            x0.append(float(np.clip(offset0, offset_lb, offset_ub)))
            lb.append(float(offset_lb))
            ub.append(float(offset_ub))

        lb = np.asarray(lb, dtype=float)
        ub = np.asarray(ub, dtype=float)
        x0 = np.asarray(x0, dtype=float)

        def unpack(vec):
            amps = vec[:n_peaks]
            centers = vec[n_peaks:2 * n_peaks]
            if fit_sigma is None:
                sigmas = vec[2 * n_peaks:3 * n_peaks]
                idx_next = 3 * n_peaks
            else:
                sigmas = np.full(n_peaks, fit_sigma, dtype=float)
                idx_next = 2 * n_peaks
            bg_poly_coeffs = None
            bg_x_center = np.nan
            bg_x_scale = np.nan
            if fix_linear_bg:
                bg_slope = float(bg_slope0)
                offset = float(offset0)
            elif fit_cubic_bg:
                bg_poly_coeffs = np.asarray(vec[idx_next:idx_next + 4], dtype=float)
                bg_x_center = float(bg_x_center0)
                bg_x_scale = float(bg_x_scale0)
                bg_slope, offset = self._legacy_linear_from_cubic(
                    bg_poly_coeffs,
                    bg_x_center=bg_x_center,
                    bg_x_scale=bg_x_scale,
                )
            else:
                bg_slope = 0.0
                offset = float(vec[idx_next])
            return amps, centers, sigmas, bg_slope, offset, bg_poly_coeffs, bg_x_center, bg_x_scale

        noise = float(np.nanstd(y_fit)) if np.isfinite(np.nanstd(y_fit)) else 1.0
        pen_scale = max(1e-3, 4.0 * noise)

        def resid(vec):
            amps, centers, sigmas, bg_slope, offset, bg_poly_coeffs, bg_x_center, bg_x_scale = unpack(vec)
            model = self._sum_model(
                bias_fit,
                amps,
                centers,
                sigmas,
                offset=offset,
                bg_slope=bg_slope,
                bg_poly_coeffs=bg_poly_coeffs,
                bg_x_center=bg_x_center,
                bg_x_scale=bg_x_scale,
                peak_profile=peak_profile,
            )
            r = model - y_fit
            dc = np.diff(np.sort(centers))
            if dc.size:
                overlap = np.clip(min_sep - dc, 0.0, None)
                if np.any(overlap > 0):
                    r = np.concatenate([r, overlap * pen_scale])
            return r

        try:
            opt = least_squares(resid, x0, bounds=(lb, ub), method="trf", max_nfev=2000)
            amps, centers, sigmas, bg_slope, offset, bg_poly_coeffs, bg_x_center, bg_x_scale = unpack(opt.x)
            order = np.argsort(centers)
            amps = amps[order]
            centers = centers[order]
            sigmas = sigmas[order]
            y_model = self._sum_model(
                bias_fit,
                amps,
                centers,
                sigmas,
                offset=offset,
                bg_slope=bg_slope,
                bg_poly_coeffs=bg_poly_coeffs,
                bg_x_center=bg_x_center,
                bg_x_scale=bg_x_scale,
                peak_profile=peak_profile,
            )
            chi2 = float(np.sum((y_model - y_fit) ** 2))
            r2 = self._safe_r2(y_fit, y_model)
            return PeakFitResult(
                amps=amps,
                centers=centers,
                sigmas=sigmas,
                offset=float(offset),
                bg_slope=float(bg_slope),
                chi2=chi2,
                r2=r2,
                success=bool(opt.success and np.all(np.isfinite(opt.x))),
                message=str(opt.message),
                peak_profile=peak_profile,
                background_mode=background_mode,
                bg_poly_coeffs=None if bg_poly_coeffs is None else np.asarray(bg_poly_coeffs, dtype=float),
                bg_x_center=float(bg_x_center),
                bg_x_scale=float(bg_x_scale),
                fit_min=fit_min,
                fit_max=fit_max,
            )
        except Exception as exc:
            return PeakFitResult(
                amps=np.full(n_peaks, np.nan),
                centers=np.full(n_peaks, np.nan),
                sigmas=np.full(n_peaks, np.nan),
                offset=np.nan,
                bg_slope=np.nan,
                chi2=np.inf,
                r2=-np.inf,
                success=False,
                message=f"Fit error: {exc}",
                peak_profile=peak_profile,
                background_mode=background_mode,
                fit_min=fit_min,
                fit_max=fit_max,
            )

    def _extract_data(self, n_peaks, min_r2=None):
        self.extracted_peaks = {
            i: {
                "E": np.full(self.n_pos, np.nan, dtype=float),
                "Sigma": np.full(self.n_pos, np.nan, dtype=float),
                "Amp": np.full(self.n_pos, np.nan, dtype=float),
            }
            for i in range(n_peaks)
        }
        self.quality[:] = np.nan

        for row, res in enumerate(self.fit_results):
            if res is None:
                continue
            self.quality[row] = float(res.r2)
            if min_r2 is not None:
                if (not np.isfinite(res.r2)) or (float(res.r2) < float(min_r2)):
                    # Keep quality for diagnostics, but do not connect peak tracks on poor rows.
                    continue
            peak_valid = getattr(res, "peak_valid", None)
            if not isinstance(peak_valid, np.ndarray) or peak_valid.size != res.centers.size:
                peak_valid = np.ones(res.centers.size, dtype=bool)
            for i in range(n_peaks):
                if i < res.centers.size and bool(peak_valid[i]):
                    self.extracted_peaks[i]["E"][row] = float(res.centers[i])
                    self.extracted_peaks[i]["Sigma"][row] = float(res.sigmas[i])
                    self.extracted_peaks[i]["Amp"][row] = float(res.amps[i])

    def run_fit(
        self,
        n_peaks=4,
        peak_count_map=None,
        fit_range=(-2.0, 2.0),
        retry_count=2,
        r2_threshold=0.8,
        peak_snr_min=2.0,
        peak_amp_frac_min=0.03,
        row_start=None,
        row_end=None,
        manual_init_centers=None,
        fixed_sigma=None,
        peak_profile=GAUSSIAN_PROFILE,
        background_mode=BACKGROUND_OFFSET,
    ):
        n_peaks = int(max(1, n_peaks))
        peak_profile = _normalize_peak_profile(peak_profile)
        background_mode = _normalize_background_mode(background_mode)
        self.last_peak_profile = peak_profile
        self.last_background_mode = background_mode
        fit_min = float(min(fit_range))
        fit_max = float(max(fit_range))
        if fit_max <= fit_min:
            raise ValueError("Fit range must satisfy max > min.")
        if self.n_pos <= 0:
            raise ValueError("No linecut row available for fitting.")

        if row_start is None:
            row_start = 0
        if row_end is None:
            row_end = self.n_pos - 1
        row_start = int(np.clip(int(row_start), 0, max(0, self.n_pos - 1)))
        row_end = int(np.clip(int(row_end), 0, max(0, self.n_pos - 1)))
        if row_end < row_start:
            raise ValueError("Selected linecut row range is invalid.")
        fit_row_count = int(row_end - row_start + 1)

        mask = (self.bias >= fit_min) & (self.bias <= fit_max)
        if np.count_nonzero(mask) < 8:
            raise ValueError("Fit range contains too few data points.")

        self.fit_results = [None] * self.n_pos
        bias_fit = self.bias[mask]
        manual_map = manual_init_centers if isinstance(manual_init_centers, dict) else {}
        peak_count_map = peak_count_map if isinstance(peak_count_map, dict) else {}
        span = max(1e-6, fit_max - fit_min)

        self._log(f"Scale factor: {self.scale_factor:.3e}")
        self._log(f"Row range: {row_start}..{row_end} ({fit_row_count}/{self.n_pos})")
        self._log(f"Points in fit range: {bias_fit.size}")

        rows = list(range(row_start, row_end + 1))
        total = len(rows)
        row_peak_counts_used = {}
        max_n_peaks = 0
        for idx_i, row in enumerate(rows):
            n_peaks_row = int(max(1, peak_count_map.get(int(row), n_peaks)))
            row_peak_counts_used[int(row)] = n_peaks_row
            max_n_peaks = max(max_n_peaks, n_peaks_row)
            y_row_full = self.data[row]
            y_row = y_row_full[mask]
            _, _, auto_guess, _, _ = self._prepare_seed_signal(
                x=self.bias,
                y=y_row_full,
                n_peaks=n_peaks_row,
                fit_range=(fit_min, fit_max),
                background_mode=background_mode,
                peak_profile=peak_profile,
                fixed_sigma=fixed_sigma,
            )
            manual_c = self._clean_centers(
                manual_map.get(int(row), None),
                (fit_min, fit_max),
                max_count=n_peaks_row,
            )
            if manual_c.size > 0:
                init_c = self._merge_initial_centers(
                    manual_c,
                    auto_guess,
                    n_peaks_row,
                    (fit_min, fit_max),
                )
            else:
                init_c = self._merge_initial_centers(
                    auto_guess,
                    np.linspace(fit_min, fit_max, n_peaks_row, dtype=float),
                    n_peaks_row,
                    (fit_min, fit_max),
                )
            res = self._fit_single_position(
                y_fit=y_row,
                bias_fit=bias_fit,
                n_peaks=n_peaks_row,
                fit_range=(fit_min, fit_max),
                init_centers=init_c,
                fixed_sigma=fixed_sigma,
                peak_profile=peak_profile,
                background_mode=background_mode,
                full_bias=self.bias,
                full_row=y_row_full,
            )
            res = self._annotate_peak_validity(
                res,
                y_row,
                bias_fit,
                (fit_min, fit_max),
                peak_snr_min=peak_snr_min,
                peak_amp_frac_min=peak_amp_frac_min,
            )

            if bool(getattr(res, "success", False)):
                best_res = res
                try:
                    model_best = self._sum_model(
                        bias_fit,
                        np.asarray(best_res.amps, dtype=float),
                        np.asarray(best_res.centers, dtype=float),
                        np.asarray(best_res.sigmas, dtype=float),
                        offset=getattr(best_res, "offset", 0.0),
                        bg_slope=getattr(best_res, "bg_slope", 0.0),
                        bg_poly_coeffs=getattr(best_res, "bg_poly_coeffs", None),
                        bg_x_center=getattr(best_res, "bg_x_center", 0.0),
                        bg_x_scale=getattr(best_res, "bg_x_scale", 1.0),
                        peak_profile=getattr(best_res, "peak_profile", peak_profile),
                    )
                except Exception:
                    model_best = None
                if model_best is not None:
                    guided_cands = self._residual_peak_candidates(
                        y_fit=y_row,
                        bias_fit=bias_fit,
                        fit_range=(fit_min, fit_max),
                        current_centers=np.asarray(best_res.centers, dtype=float),
                        model_y=model_best,
                        max_count=min(max(1, n_peaks_row), 3),
                    )
                    if guided_cands.size:
                        replace_order = self._replacement_order(
                            best_res,
                            protected_centers=manual_c if manual_c.size > 0 else None,
                            fit_range=(fit_min, fit_max),
                        )
                        max_replace = min(max(1, replace_order.size), max(2, min(n_peaks_row, 4)))
                        for cand_c in np.asarray(guided_cands, dtype=float):
                            for rep_idx in np.asarray(replace_order[:max_replace], dtype=int):
                                c_try = np.asarray(best_res.centers, dtype=float).copy()
                                if rep_idx < 0 or rep_idx >= c_try.size:
                                    continue
                                c_try[int(rep_idx)] = float(cand_c)
                                c_try = self._merge_initial_centers(
                                    c_try,
                                    np.asarray(best_res.centers, dtype=float),
                                    n_peaks_row,
                                    (fit_min, fit_max),
                                )
                                res_try = self._fit_single_position(
                                    y_fit=y_row,
                                    bias_fit=bias_fit,
                                    n_peaks=n_peaks_row,
                                    fit_range=(fit_min, fit_max),
                                    init_centers=c_try,
                                    fixed_sigma=fixed_sigma,
                                    peak_profile=peak_profile,
                                    background_mode=background_mode,
                                    full_bias=self.bias,
                                    full_row=y_row_full,
                                )
                                res_try = self._annotate_peak_validity(
                                    res_try,
                                    y_row,
                                    bias_fit,
                                    (fit_min, fit_max),
                                    peak_snr_min=peak_snr_min,
                                    peak_amp_frac_min=peak_amp_frac_min,
                                )
                                if res_try.chi2 < best_res.chi2:
                                    best_res = res_try
                        res = best_res

            if not self._is_good_fit(res, r2_threshold):
                best_res = res
                n_retry = max(1, int(retry_count))
                for _ in range(n_retry):
                    c_try = np.sort(
                        np.asarray(init_c, dtype=float)
                        + np.random.uniform(-0.03 * span, 0.03 * span, size=np.asarray(init_c, dtype=float).shape)
                    )
                    res_retry = self._fit_single_position(
                        y_fit=y_row,
                        bias_fit=bias_fit,
                        n_peaks=n_peaks_row,
                        fit_range=(fit_min, fit_max),
                        init_centers=c_try,
                        fixed_sigma=fixed_sigma,
                        peak_profile=peak_profile,
                        background_mode=background_mode,
                        full_bias=self.bias,
                        full_row=y_row_full,
                    )
                    res_retry = self._annotate_peak_validity(
                        res_retry,
                        y_row,
                        bias_fit,
                        (fit_min, fit_max),
                        peak_snr_min=peak_snr_min,
                        peak_amp_frac_min=peak_amp_frac_min,
                    )
                    if res_retry.chi2 < best_res.chi2:
                        best_res = res_retry
                res = best_res

            self.fit_results[row] = res

            if idx_i % max(1, total // 8) == 0:
                self._log(f"Independent fit: {idx_i + 1}/{max(1, total)}")
            if self._process_events is not None and idx_i % 4 == 0:
                self._process_events()

        max_n_peaks = max(1, int(max_n_peaks))
        self._extract_data(max_n_peaks, min_r2=float(r2_threshold))

        valid = [
            r for idx, r in enumerate(self.fit_results)
            if (row_start <= idx <= row_end) and (r is not None) and r.success
        ]
        good = [r for r in valid if r.r2 >= float(r2_threshold)]
        mean_r2 = float(np.mean([r.r2 for r in valid])) if valid else float("nan")
        detected_count = 0
        for i in range(max_n_peaks):
            e_row = np.asarray(self.extracted_peaks[i]["E"][row_start:row_end + 1], dtype=float)
            detected_count += int(np.count_nonzero(np.isfinite(e_row)))
        total_slots = int(sum(int(row_peak_counts_used.get(int(row), n_peaks)) for row in rows))
        self._log(
            f"Fitting done. valid={len(valid)}/{fit_row_count}, "
            f"good={len(good)}/{fit_row_count}, mean r2={mean_r2:.4f}"
        )

        return {
            "valid_count": len(valid),
            "good_count": len(good),
            "total_count": fit_row_count,
            "mean_r2": mean_r2,
            "detected_count": detected_count,
            "total_slots": total_slots,
            "n_peaks": n_peaks,
            "default_n_peaks": int(n_peaks),
            "max_n_peaks": int(max_n_peaks),
            "row_peak_counts": {int(k): int(v) for k, v in row_peak_counts_used.items()},
            "fit_range": (fit_min, fit_max),
            "peak_snr_min": float(peak_snr_min),
            "peak_amp_frac_min": float(peak_amp_frac_min),
            "fit_row_start": int(row_start),
            "fit_row_end": int(row_end),
            "fit_row_count": int(fit_row_count),
            "total_rows": int(self.n_pos),
            "fixed_sigma": None if fixed_sigma is None else float(fixed_sigma),
            "fixed_width": None if fixed_sigma is None else float(fixed_sigma),
            "width_parameter": _peak_width_label(peak_profile),
            "peak_profile": str(peak_profile),
            "background_mode": str(background_mode),
        }

    def evaluate_at(self, row_idx, x_axis=None):
        if row_idx < 0 or row_idx >= self.n_pos:
            return None
        res = self.fit_results[row_idx]
        if res is None or not res.success:
            return None

        x = self.bias if x_axis is None else np.asarray(x_axis, dtype=float)
        peak_profile = getattr(res, "peak_profile", self.last_peak_profile)
        bg = self._background_model(
            x,
            offset=getattr(res, "offset", 0.0),
            bg_slope=getattr(res, "bg_slope", 0.0),
            bg_poly_coeffs=getattr(res, "bg_poly_coeffs", None),
            bg_x_center=getattr(res, "bg_x_center", 0.0),
            bg_x_scale=getattr(res, "bg_x_scale", 1.0),
        )
        comps = [
            self._peak_model(x, a, c, s, peak_profile=peak_profile)
            for a, c, s in zip(res.amps, res.centers, res.sigmas)
        ]
        total = self._sum_model(
            x,
            res.amps,
            res.centers,
            res.sigmas,
            offset=getattr(res, "offset", 0.0),
            bg_slope=getattr(res, "bg_slope", 0.0),
            bg_poly_coeffs=getattr(res, "bg_poly_coeffs", None),
            bg_x_center=getattr(res, "bg_x_center", 0.0),
            bg_x_scale=getattr(res, "bg_x_scale", 1.0),
            peak_profile=peak_profile,
        )
        peak_valid = getattr(res, "peak_valid", None)
        if not isinstance(peak_valid, np.ndarray) or peak_valid.size != len(comps):
            peak_valid = np.ones(len(comps), dtype=bool)
        return total, comps, np.asarray(peak_valid, dtype=bool), np.asarray(bg, dtype=float)

    def collect_debug_state_payload(self, n_peaks=None):
        if n_peaks is None:
            n_peaks = 0
            if self.fit_results:
                for res in self.fit_results:
                    if res is not None and np.asarray(getattr(res, "centers", np.zeros(0, dtype=float))).size:
                        n_peaks = int(np.asarray(res.centers, dtype=float).size)
                        break

        n_peaks = int(max(0, n_peaks))
        if n_peaks <= 0:
            raise ValueError("No valid fitting result to save.")

        amps = np.full((self.n_pos, n_peaks), np.nan, dtype=float)
        centers = np.full((self.n_pos, n_peaks), np.nan, dtype=float)
        sigmas = np.full((self.n_pos, n_peaks), np.nan, dtype=float)
        peak_valid = np.zeros((self.n_pos, n_peaks), dtype=np.uint8)
        peak_snr = np.full((self.n_pos, n_peaks), np.nan, dtype=float)
        bg_slope = np.zeros(self.n_pos, dtype=float)
        bg_intercept = np.full(self.n_pos, np.nan, dtype=float)
        bg_poly_coeffs = np.full((self.n_pos, 4), np.nan, dtype=float)
        bg_x_center = np.full(self.n_pos, np.nan, dtype=float)
        bg_x_scale = np.full(self.n_pos, np.nan, dtype=float)
        fit_min = np.full(self.n_pos, np.nan, dtype=float)
        fit_max = np.full(self.n_pos, np.nan, dtype=float)
        chisqr = np.full(self.n_pos, np.nan, dtype=float)
        r2 = np.full(self.n_pos, np.nan, dtype=float)
        peak_profile = str(self.last_peak_profile)
        background_mode = str(self.last_background_mode)

        for i, res in enumerate(self.fit_results):
            if res is None:
                continue
            k = min(n_peaks, int(np.asarray(res.centers, dtype=float).size))
            if k > 0:
                amps[i, :k] = np.asarray(res.amps[:k], dtype=float)
                centers[i, :k] = np.asarray(res.centers[:k], dtype=float)
                sigmas[i, :k] = np.asarray(res.sigmas[:k], dtype=float)
                pv = getattr(res, "peak_valid", None)
                if isinstance(pv, np.ndarray) and pv.size >= k:
                    peak_valid[i, :k] = np.asarray(pv[:k], dtype=np.uint8)
                else:
                    peak_valid[i, :k] = 1
                ps = getattr(res, "peak_snr", None)
                if isinstance(ps, np.ndarray) and ps.size >= k:
                    peak_snr[i, :k] = np.asarray(ps[:k], dtype=float)
            peak_profile = str(getattr(res, "peak_profile", peak_profile) or peak_profile)
            background_mode = str(getattr(res, "background_mode", background_mode) or background_mode)
            bg_slope[i] = float(getattr(res, "bg_slope", 0.0)) / float(self.scale_factor)
            bg_intercept[i] = float(getattr(res, "offset", np.nan)) / float(self.scale_factor)
            bg_poly_src = getattr(res, "bg_poly_coeffs", None)
            bg_poly = np.asarray(bg_poly_src if bg_poly_src is not None else [], dtype=float).ravel()
            if bg_poly.size >= 4 and np.all(np.isfinite(bg_poly[:4])):
                bg_poly_coeffs[i, :] = np.asarray(bg_poly[:4], dtype=float) / float(self.scale_factor)
                bg_x_center[i] = float(getattr(res, "bg_x_center", np.nan))
                bg_x_scale[i] = float(getattr(res, "bg_x_scale", np.nan))
            fit_min[i] = float(getattr(res, "fit_min", np.nan))
            fit_max[i] = float(getattr(res, "fit_max", np.nan))
            chisqr[i] = float(getattr(res, "chi2", np.nan))
            r2[i] = float(getattr(res, "r2", np.nan))

        return {
            "raw_data": np.asarray(self.data_raw, dtype=float),
            "fit_data_scaled": np.asarray(self.data, dtype=float),
            "bias": np.asarray(self.bias, dtype=float),
            "pos": np.asarray(self.pos, dtype=float),
            "amps": np.asarray(amps, dtype=float) / float(self.scale_factor),
            "centers": np.asarray(centers, dtype=float),
            "sigmas": np.asarray(sigmas, dtype=float),
            "peak_valid": np.asarray(peak_valid, dtype=np.uint8),
            "peak_snr": np.asarray(peak_snr, dtype=float),
            "bg_slope": np.asarray(bg_slope, dtype=float),
            "bg_intercept": np.asarray(bg_intercept, dtype=float),
            "bg_poly_coeffs": np.asarray(bg_poly_coeffs, dtype=float),
            "bg_x_center": np.asarray(bg_x_center, dtype=float),
            "bg_x_scale": np.asarray(bg_x_scale, dtype=float),
            "fit_min": np.asarray(fit_min, dtype=float),
            "fit_max": np.asarray(fit_max, dtype=float),
            "chisqr": np.asarray(chisqr, dtype=float),
            "r2": np.asarray(r2, dtype=float),
            "n_peaks": int(n_peaks),
            "scale_factor": float(self.scale_factor),
            "peak_profile": np.asarray(str(peak_profile)),
            "background_mode": np.asarray(str(background_mode)),
        }

    def save_debug_state(self, filename, n_peaks=None):
        np.savez_compressed(filename, **self.collect_debug_state_payload(n_peaks=n_peaks))



_MULTIPEAK_SOURCE_MAPPING = (
    "linecutmap_multipeak_fitting.PeakFitResult and "
    "UniversalVortexFitterEngine.run_fit/evaluate_at/collect_debug_state_payload"
)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _summary_from_engine(engine: UniversalVortexFitterEngine, n_peaks: int, summary: dict[str, Any]) -> dict[str, Any]:
    payload = engine.collect_debug_state_payload(n_peaks=n_peaks)
    r2 = np.asarray(payload.get("r2", []), dtype=float)
    centers = np.asarray(payload.get("centers", []), dtype=float)
    peak_valid = np.asarray(payload.get("peak_valid", []), dtype=np.uint8)
    successful = int(summary.get("successful_fits", summary.get("valid_count", 0))) if isinstance(summary, dict) else 0
    good = int(summary.get("good_fits", summary.get("good_count", 0))) if isinstance(summary, dict) else 0
    finite_r2 = r2[np.isfinite(r2)]
    out = dict(summary or {})
    out.update(
        {
            "n_positions": int(engine.n_pos),
            "n_peaks": int(n_peaks),
            "successful_fits": successful,
            "good_fits": good,
            "finite_r2_count": int(finite_r2.size),
            "median_r2": float(np.nanmedian(finite_r2)) if finite_r2.size else np.nan,
            "valid_peak_count": int(np.count_nonzero(peak_valid)),
            "finite_center_count": int(np.count_nonzero(np.isfinite(centers))),
        }
    )
    return out


def run_multipeak_fit(
    bias,
    position,
    data,
    *,
    n_peaks: int = 4,
    peak_count_map: dict[int, int] | None = None,
    fit_range: tuple[float, float] = (-2.0, 2.0),
    retry_count: int = 2,
    r2_threshold: float = 0.8,
    peak_snr_min: float = 2.0,
    peak_amp_frac_min: float = 0.03,
    row_start: int | None = None,
    row_end: int | None = None,
    manual_init_centers: dict[int, list[float]] | None = None,
    fixed_sigma: float | None = None,
    peak_profile: str = GAUSSIAN_PROFILE,
    background_mode: str = BACKGROUND_OFFSET,
    random_seed: int | None = None,
    log_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the migrated PySIDAM UniversalVortexFitterEngine as a public backend."""

    if random_seed is not None:
        np.random.seed(int(random_seed))
    engine = UniversalVortexFitterEngine(bias, position, data, log_fn=log_fn)
    summary = engine.run_fit(
        n_peaks=n_peaks,
        peak_count_map=peak_count_map,
        fit_range=fit_range,
        retry_count=retry_count,
        r2_threshold=r2_threshold,
        peak_snr_min=peak_snr_min,
        peak_amp_frac_min=peak_amp_frac_min,
        row_start=row_start,
        row_end=row_end,
        manual_init_centers=manual_init_centers,
        fixed_sigma=fixed_sigma,
        peak_profile=peak_profile,
        background_mode=background_mode,
    )
    payload_n_peaks = int(summary.get("max_n_peaks", n_peaks)) if isinstance(summary, dict) else int(n_peaks)
    payload = engine.collect_debug_state_payload(n_peaks=payload_n_peaks)
    summary_public = _summary_from_engine(engine, payload_n_peaks, summary if isinstance(summary, dict) else {})
    parameters = {
        "n_peaks": int(n_peaks),
        "peak_count_map": _to_jsonable(peak_count_map or {}),
        "fit_range": [float(min(fit_range)), float(max(fit_range))],
        "retry_count": int(retry_count),
        "r2_threshold": float(r2_threshold),
        "peak_snr_min": float(peak_snr_min),
        "peak_amp_frac_min": float(peak_amp_frac_min),
        "row_start": None if row_start is None else int(row_start),
        "row_end": None if row_end is None else int(row_end),
        "manual_init_centers": _to_jsonable(manual_init_centers or {}),
        "fixed_sigma": None if fixed_sigma is None else float(fixed_sigma),
        "peak_profile": _normalize_peak_profile(peak_profile),
        "background_mode": _normalize_background_mode(background_mode),
        "random_seed": None if random_seed is None else int(random_seed),
    }
    return {
        "schema_version": 1,
        "algorithm": {
            "name": "AnalySTM multipeak fitting backend",
            "engine": "analystm.multipeak.run_multipeak_fit",
            "pysidam_source_mapping": _MULTIPEAK_SOURCE_MAPPING,
            "replacement_scope": "migrated non-GUI UniversalVortexFitterEngine backend",
        },
        "parameters": parameters,
        "summary": summary_public,
        "outputs": payload,
        "engine": engine,
    }


__all__ = [
    "BACKGROUND_FULL_TRACE_LINEAR",
    "BACKGROUND_IGOR_CUBIC",
    "BACKGROUND_OFFSET",
    "GAUSSIAN_PROFILE",
    "LORENTZIAN_PROFILE",
    "MAX_MULTIPEAK_COUNT",
    "PeakFitResult",
    "UniversalVortexFitterEngine",
    "run_multipeak_fit",
]
