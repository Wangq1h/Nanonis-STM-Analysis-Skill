from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import interpolate
from scipy.fft import fft2, fftshift, ifft2, ifftshift
from scipy.optimize import curve_fit

try:
    from skimage.restoration import unwrap_phase as _unwrap_phase

    HAS_SKIMAGE = True
except Exception:
    _unwrap_phase = None
    HAS_SKIMAGE = False


LF_SOURCE_MAPPING = "topography_correction.LFDriftCorrector.compute_drift_field and warp_image"
LF_QPI_SOURCE_MAPPING = (
    "topography_correction.LFDriftCorrector plus "
    "qpi_symmetry.estimate_lf_displacement_from_q_vectors and apply_lf_displacement_to_stack"
)


def topography_algorithm(engine: str, *, source_mapping: str = LF_SOURCE_MAPPING) -> dict[str, str]:
    return {
        "name": "AnalySTM topography backend",
        "engine": engine,
        "pysidam_source_mapping": source_mapping,
    }


def identity_lf_corr_coords(shape_yx: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    h, w = int(shape_yx[0]), int(shape_yx[1])
    yy, xx = np.mgrid[:h, :w]
    return np.asarray(yy, dtype=float), np.asarray(xx, dtype=float)


def lf_q_vector_from_fft_pixel(shape_yx: Sequence[int], py: float, px: float) -> np.ndarray:
    h, w = int(shape_yx[0]), int(shape_yx[1])
    cy, cx = h // 2, w // 2
    qy = 2.0 * np.pi * (float(py) - cy) / float(h)
    qx = 2.0 * np.pi * (float(px) - cx) / float(w)
    return np.asarray([qy, qx], dtype=float)


class LFDriftCorrector:
    def __init__(self, image: Any):
        self.image = np.asarray(image, dtype=float)
        if self.image.ndim != 2:
            raise ValueError("LFDriftCorrector expects a 2D topography image.")
        self.H, self.W = self.image.shape
        self.y, self.x = np.mgrid[: self.H, : self.W]

        self.Z_fft = fftshift(fft2(self.image))
        self.P = np.abs(self.Z_fft)

        self.q_vectors: list[np.ndarray] = []
        self.drift_field: tuple[np.ndarray, np.ndarray] | None = None
        self.image_corr: np.ndarray | None = None
        self.corr_coords: tuple[np.ndarray, np.ndarray] | None = None
        self.ux_field: np.ndarray | None = None
        self.uy_field: np.ndarray | None = None

    def refine_peak_local_max(self, click_y: float, click_x: float, search_r: int = 3) -> tuple[float, float]:
        y_int, x_int = int(click_y), int(click_x)
        y0, y1 = max(0, y_int - int(search_r)), min(self.H, y_int + int(search_r) + 1)
        x0, x1 = max(0, x_int - int(search_r)), min(self.W, x_int + int(search_r) + 1)

        sub_region = self.P[y0:y1, x0:x1]
        if sub_region.size == 0:
            return float(click_y), float(click_x)

        py, px = np.unravel_index(np.argmax(sub_region), sub_region.shape)
        return float(y0 + py), float(x0 + px)

    def refine_peak_gaussian(self, click_y: float, click_x: float, fit_r: int = 3) -> tuple[float, float]:
        y_int = int(round(click_y))
        x_int = int(round(click_x))
        fit_r = int(fit_r)
        y0, y1 = max(0, y_int - fit_r), min(self.H, y_int + fit_r + 1)
        x0, x1 = max(0, x_int - fit_r), min(self.W, x_int + fit_r + 1)

        sub_region = np.asarray(self.P[y0:y1, x0:x1], dtype=float)
        if sub_region.shape[0] < 3 or sub_region.shape[1] < 3:
            return float(click_y), float(click_x)
        if not np.isfinite(sub_region).any():
            return float(click_y), float(click_x)

        peak_idx = np.unravel_index(np.nanargmax(sub_region), sub_region.shape)
        peak_y = float(y0 + peak_idx[0])
        peak_x = float(x0 + peak_idx[1])
        peak_val = float(np.nanmax(sub_region))
        base_val = float(np.nanpercentile(sub_region, 20))
        amp0 = peak_val - base_val
        if not np.isfinite(amp0) or amp0 <= 0:
            return float(click_y), float(click_x)

        yy, xx = np.mgrid[y0:y1, x0:x1]

        def gaussian_2d(coords, amp, yc, xc, sy, sx, offset):
            y_arr, x_arr = coords
            expo = ((y_arr - yc) / sy) ** 2 + ((x_arr - xc) / sx) ** 2
            return offset + amp * np.exp(-0.5 * expo)

        sigma0 = max(0.8, float(fit_r) / 2.0)
        p0 = [amp0, peak_y, peak_x, sigma0, sigma0, base_val]
        lower = [0.0, y0 - 0.5, x0 - 0.5, 0.35, 0.35, float(np.nanmin(sub_region) - abs(amp0))]
        upper = [
            float(max(peak_val * 2.0, amp0 * 3.0 + abs(base_val) + 1.0)),
            y1 - 0.5,
            x1 - 0.5,
            max(1.0, 2.0 * fit_r + 1.0),
            max(1.0, 2.0 * fit_r + 1.0),
            float(np.nanmax(sub_region) + abs(amp0)),
        ]
        try:
            popt, _ = curve_fit(
                gaussian_2d,
                (yy.ravel(), xx.ravel()),
                sub_region.ravel(),
                p0=p0,
                bounds=(lower, upper),
                maxfev=8000,
            )
        except Exception:
            return float(click_y), float(click_x)

        fit_y = float(popt[1])
        fit_x = float(popt[2])
        if not np.isfinite(fit_y) or not np.isfinite(fit_x):
            return float(click_y), float(click_x)
        if abs(fit_y - float(click_y)) > max(1.5, fit_r + 0.5):
            return float(click_y), float(click_x)
        if abs(fit_x - float(click_x)) > max(1.5, fit_r + 0.5):
            return float(click_y), float(click_x)
        return fit_y, fit_x

    def refine_peak(
        self,
        click_y: float,
        click_x: float,
        search_r: int = 3,
        use_local_max: bool = True,
        use_gaussian: bool = False,
        gaussian_r: int = 3,
    ) -> tuple[float, float]:
        y_ref = float(click_y)
        x_ref = float(click_x)
        if use_local_max:
            y_ref, x_ref = self.refine_peak_local_max(y_ref, x_ref, search_r=search_r)
        if use_gaussian:
            y_ref, x_ref = self.refine_peak_gaussian(y_ref, x_ref, fit_r=gaussian_r)
        return y_ref, x_ref

    def get_q_vector(self, py: float, px: float) -> np.ndarray:
        return lf_q_vector_from_fft_pixel((self.H, self.W), py, px)

    def lockin_phase(self, q_vec: Sequence[float], sigma: float = 3.0) -> np.ndarray:
        if not HAS_SKIMAGE or _unwrap_phase is None:
            raise RuntimeError("scikit-image is required for unwrap_phase.")
        qy, qx = np.asarray(q_vec, dtype=float).ravel()[:2]
        ref_wave = np.exp(-1j * (qy * self.y + qx * self.x))
        demod = self.image * ref_wave

        f_demod = fftshift(fft2(demod))
        cy, cx = self.H // 2, self.W // 2
        r2 = (self.y - cy) ** 2 + (self.x - cx) ** 2
        lp_mask = np.exp(-r2 / (2.0 * float(sigma) ** 2))

        filtered = ifft2(ifftshift(f_demod * lp_mask))
        phase = np.angle(filtered)
        return np.asarray(_unwrap_phase(phase), dtype=float)

    def compute_drift_field(self, q1: Sequence[float], q2: Sequence[float], sigma: float = 3.0) -> tuple[np.ndarray | None, np.ndarray | None]:
        phi1 = self.lockin_phase(q1, sigma=float(sigma))
        phi2 = self.lockin_phase(q2, sigma=float(sigma))
        package = compute_lf_drift_field_from_phases(phi1, phi2, q1_yx=q1, q2_yx=q2)
        if not package["valid"]:
            self.drift_field = None
            self.corr_coords = None
            self.ux_field = None
            self.uy_field = None
            return None, None

        uy_down = np.asarray(package["uy_down_field"], dtype=float)
        ux = np.asarray(package["ux_field"], dtype=float)
        self.drift_field = (uy_down, ux)
        self.corr_coords = (np.asarray(package["corr_coords_y"], dtype=float), np.asarray(package["corr_coords_x"], dtype=float))
        self.uy_field = np.asarray(package["uy_field"], dtype=float)
        self.ux_field = ux
        return self.uy_field, ux

    def warp_image(self) -> np.ndarray:
        if self.drift_field is None or self.corr_coords is None:
            return self.image
        self.image_corr = apply_lf_displacement_to_stack(self.image, self.corr_coords)
        return self.image_corr


def compute_lf_drift_field_from_phases(
    phi1: Any,
    phi2: Any,
    *,
    q1_yx: Sequence[float],
    q2_yx: Sequence[float],
) -> dict[str, Any]:
    p1 = np.asarray(phi1, dtype=float)
    p2 = np.asarray(phi2, dtype=float)
    if p1.shape != p2.shape or p1.ndim != 2:
        raise ValueError("LF drift phase fields must be two 2D arrays with matching shape.")
    q1 = np.asarray(q1_yx, dtype=float).ravel()
    q2 = np.asarray(q2_yx, dtype=float).ravel()
    if q1.size < 2 or q2.size < 2:
        raise ValueError("LF drift q vectors must contain qy,qx.")

    d_phi1 = p1 - np.mean(p1)
    d_phi2 = p2 - np.mean(p2)
    det = q1[0] * q2[1] - q1[1] * q2[0]
    yy, xx = identity_lf_corr_coords(p1.shape)
    if abs(float(det)) < 1e-8:
        nan_field = np.full_like(p1, np.nan, dtype=float)
        return {
            "valid": False,
            "uy_down_field": nan_field,
            "uy_field": nan_field,
            "ux_field": nan_field,
            "corr_coords_y": yy,
            "corr_coords_x": xx,
            "algorithm": topography_algorithm("analystm.topography.compute_lf_drift_field_from_phases"),
            "parameters": {"q1_yx": [float(q1[0]), float(q1[1])], "q2_yx": [float(q2[0]), float(q2[1])]},
        }

    uy_down = (d_phi1 * q2[1] - d_phi2 * q1[1]) / det
    ux = (d_phi2 * q1[0] - d_phi1 * q2[0]) / det
    corr_y = yy + uy_down
    corr_x = xx + ux
    return {
        "valid": True,
        "uy_down_field": np.asarray(uy_down, dtype=float),
        "uy_field": np.asarray(-uy_down, dtype=float),
        "ux_field": np.asarray(ux, dtype=float),
        "corr_coords_y": np.asarray(corr_y, dtype=float),
        "corr_coords_x": np.asarray(corr_x, dtype=float),
        "algorithm": topography_algorithm("analystm.topography.compute_lf_drift_field_from_phases"),
        "parameters": {"q1_yx": [float(q1[0]), float(q1[1])], "q2_yx": [float(q2[0]), float(q2[1])]},
    }


def estimate_lf_displacement_from_q_vectors(reference_image: Any, q1_yx: Sequence[float], q2_yx: Sequence[float], sigma: float = 3.0) -> dict[str, Any]:
    corrector = LFDriftCorrector(reference_image)
    uy, ux = corrector.compute_drift_field(q1_yx, q2_yx, sigma=float(sigma))
    if uy is None or ux is None or corrector.corr_coords is None:
        raise ValueError("LF drift q vectors are colinear or could not produce a displacement field.")
    corrected = corrector.warp_image()
    cy, cx = corrector.corr_coords
    return {
        "corrected_image": np.asarray(corrected, dtype=float),
        "uy_field": np.asarray(corrector.uy_field, dtype=float),
        "ux_field": np.asarray(corrector.ux_field, dtype=float),
        "corr_coords_y": np.asarray(cy, dtype=float),
        "corr_coords_x": np.asarray(cx, dtype=float),
        "q_vectors_yx": np.asarray([q1_yx, q2_yx], dtype=float),
        "algorithm": topography_algorithm(
            "analystm.topography.estimate_lf_displacement_from_q_vectors",
            source_mapping=LF_QPI_SOURCE_MAPPING,
        ),
        "parameters": {"sigma": float(sigma), "q1_yx": [float(q1_yx[0]), float(q1_yx[1])], "q2_yx": [float(q2_yx[0]), float(q2_yx[1])]},
        "summary": {
            "shape_yx": [int(corrector.H), int(corrector.W)],
            "ux_mean_px": float(np.nanmean(corrector.ux_field)),
            "uy_mean_px": float(np.nanmean(corrector.uy_field)),
        },
    }


def estimate_lf_displacement(
    reference_image: Any,
    q_points_px: Sequence[Sequence[float]],
    *,
    sigma: float = 3.0,
    search_r: int = 3,
    use_local_max: bool = True,
    use_gaussian: bool = False,
    gaussian_r: int = 3,
) -> dict[str, Any]:
    points = [tuple(map(float, p)) for p in q_points_px]
    if len(points) < 2:
        raise ValueError("LF drift correction requires two FFT peak points.")
    corrector = LFDriftCorrector(reference_image)
    refined = []
    for px, py in points[:2]:
        ry, rx = corrector.refine_peak(
            py,
            px,
            search_r=search_r,
            use_local_max=use_local_max,
            use_gaussian=use_gaussian,
            gaussian_r=gaussian_r,
        )
        refined.append((float(rx), float(ry)))
    q1 = corrector.get_q_vector(refined[0][1], refined[0][0])
    q2 = corrector.get_q_vector(refined[1][1], refined[1][0])
    package = estimate_lf_displacement_from_q_vectors(reference_image, q1, q2, sigma=float(sigma))
    package["q_points_px"] = np.asarray(refined, dtype=float)
    package["algorithm"] = topography_algorithm("analystm.topography.estimate_lf_displacement", source_mapping=LF_QPI_SOURCE_MAPPING)
    package["parameters"].update(
        {
            "search_r": int(search_r),
            "use_local_max": bool(use_local_max),
            "use_gaussian": bool(use_gaussian),
            "gaussian_r": int(gaussian_r),
        }
    )
    return package


def apply_lf_displacement_to_stack(data: Any, corr_coords: tuple[Any, Any]) -> np.ndarray:
    stack, was_2d = _as_stack(data)
    h, w = stack.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    cy, cx = corr_coords
    points = np.column_stack((np.asarray(cy, dtype=float).ravel(), np.asarray(cx, dtype=float).ravel()))
    out = np.empty_like(stack, dtype=float)
    for idx in range(stack.shape[2]):
        layer = np.asarray(stack[:, :, idx], dtype=float)
        values = np.nan_to_num(layer, nan=0.0, posinf=0.0, neginf=0.0).ravel()
        warped = interpolate.griddata(points, values, (yy, xx), method="linear")
        invalid = ~np.isfinite(warped)
        if np.any(invalid):
            nearest = interpolate.griddata(points, values, (yy, xx), method="nearest")
            warped[invalid] = nearest[invalid]
        out[:, :, idx] = np.nan_to_num(warped, nan=0.0, posinf=0.0, neginf=0.0)
    return np.ascontiguousarray(out if not was_2d else out[:, :, 0], dtype=float)


def _as_stack(data: Any) -> tuple[np.ndarray, bool]:
    arr = np.asarray(data, dtype=float)
    was_2d = arr.ndim == 2
    if was_2d:
        arr = arr[:, :, None]
    if arr.ndim != 3:
        raise ValueError("LF displacement expects a 2D image or 3D stack.")
    return np.ascontiguousarray(arr, dtype=float), was_2d
