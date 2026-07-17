"""AnalySTM public headless backend for STM/SJTM agent workflows."""

from importlib import import_module

__version__ = "3.0.1"

__all__ = [
    "ApprovalValidationError",
    "LFDriftCorrector",
    "PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY",
    "PeakFitResult",
    "SXMMapView",
    "UniversalVortexFitterEngine",
    "__version__",
    "apply_wipe_regions",
    "apply_lf_displacement_to_stack",
    "apply_intensity_signal_mode",
    "apply_waterfall_baseline",
    "build_domain_wall_masks",
    "build_generated_header",
    "build_nanonis_spec_header",
    "build_path_from_batches",
    "FigurePayload",
    "ImagePayload",
    "LinePayload",
    "build_linear_resample_matrix",
    "build_pinv_operator",
    "build_fft_q0_gaussian_notch_1d_discrete",
    "build_fft_roi_mask",
    "build_qpi_r90_contrast",
    "build_qpi_spin_contrast",
    "compute_z_ratio_map",
    "compute_lf_drift_field_from_phases",
    "compute_fft_base_volume",
    "compute_real_phase_pll",
    "compute_sjtm_package",
    "compute_r2_score",
    "compute_pr_qpi_volume",
    "compute_qpi_1d_fft",
    "compute_histogram",
    "compute_spectrum_derivative",
    "compute_square_crop_geometry",
    "compute_topography_fft_display",
    "domain_wall_policy",
    "extract_bias_slice",
    "extract_h_cut",
    "extract_sxm_display_map",
    "extract_v_cut",
    "extract_gap_map",
    "estimate_lf_displacement",
    "estimate_lf_displacement_from_q_vectors",
    "fit_gap_model",
    "fit_gap_model_guarded",
    "fit_gap_priority_modes",
    "identity_lf_corr_coords",
    "lattice_qc",
    "lf_q_vector_from_fft_pixel",
    "nanmean_cube_over_pixels",
    "peak_align_zero_cube",
    "process_intensity_matrix",
    "process_didv_contrast",
    "process_spectrum",
    "process_topography_display_map",
    "prepare_sxm_map",
    "payload_data_limits",
    "real_phase_lockin",
    "q_cycles_to_pysidam_px_yx",
    "run_lockin_phase",
    "run_qpi_fft",
    "run_fft_filter",
    "run_waterfall_fit",
    "sample_topography_linecut",
    "region_stats",
    "remove_linear_baseline_1d",
    "remove_linear_baseline_2d",
    "render_review_html",
    "run_sis_didv_deconvolution",
    "run_pysidam_lockin",
    "run_multipeak_fit",
    "run_qpi_symmetry",
    "scale_recommendation",
    "sample_linecut",
    "sample_display_patch",
    "select_bias_indices_in_range",
    "symmetrize_qpi",
    "validate_decision",
    "validate_proposal",
    "validate_report_links_decision",
    "write_ibw_wave",
    "write_nanonis_grid_3ds",
    "write_nanonis_spec_dat",
]


def __getattr__(name: str):
    if name in {"SXMMapView", "prepare_sxm_map"}:
        dataset_utils = import_module(".dataset_utils", __name__)
        return getattr(dataset_utils, name)
    if name in {
        "ApprovalValidationError",
        "render_review_html",
        "validate_decision",
        "validate_proposal",
        "validate_report_links_decision",
    }:
        approval = import_module(".approval", __name__)
        return getattr(approval, name)
    if name in {"fit_gap_model", "fit_gap_model_guarded"}:
        gap_fitting = import_module(".gap_fitting", __name__)
        return getattr(gap_fitting, name)
    if name in {"PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY", "fit_gap_priority_modes"}:
        gap_priority = import_module(".gap_priority", __name__)
        return getattr(gap_priority, name)
    if name in {"apply_wipe_regions", "lattice_qc", "scale_recommendation"}:
        atom_ai = import_module(".atom_ai", __name__)
        return getattr(atom_ai, name)
    if name in {"build_domain_wall_masks", "domain_wall_policy", "region_stats"}:
        domain_wall = import_module(".domain_wall", __name__)
        return getattr(domain_wall, name)
    if name in {"build_nanonis_spec_header", "write_ibw_wave", "write_nanonis_grid_3ds", "write_nanonis_spec_dat"}:
        export = import_module(".export", __name__)
        return getattr(export, name)
    if name in {"compute_histogram"}:
        histogram = import_module(".histogram", __name__)
        return getattr(histogram, name)
    if name in {"compute_topography_fft_display", "process_topography_display_map", "sample_topography_linecut"}:
        topography_display = import_module(".topography_display", __name__)
        return getattr(topography_display, name)
    if name in {"compute_spectrum_derivative", "process_spectrum"}:
        spectroscopy = import_module(".spectroscopy", __name__)
        return getattr(spectroscopy, name)
    if name in {"build_path_from_batches"}:
        path_viz = import_module(".path_viz", __name__)
        return getattr(path_viz, name)
    if name in {"FigurePayload", "ImagePayload", "LinePayload", "payload_data_limits"}:
        publication = import_module(".publication", __name__)
        return getattr(publication, name)
    if name in {"build_generated_header", "compute_square_crop_geometry", "extract_sxm_display_map", "sample_display_patch"}:
        map_crop = import_module(".map_crop", __name__)
        return getattr(map_crop, name)
    if name in {"extract_gap_map"}:
        gap_map = import_module(".gap_map", __name__)
        return getattr(gap_map, name)
    if name in {"compute_sjtm_package"}:
        sjtm = import_module(".sjtm", __name__)
        return getattr(sjtm, name)
    if name in {
        "apply_intensity_signal_mode",
        "compute_z_ratio_map",
        "extract_bias_slice",
        "extract_h_cut",
        "extract_v_cut",
        "peak_align_zero_cube",
        "process_intensity_matrix",
        "remove_linear_baseline_1d",
        "remove_linear_baseline_2d",
        "select_bias_indices_in_range",
    }:
        intensity = import_module(".intensity", __name__)
        return getattr(intensity, name)
    if name in {
        "compute_fft_base_volume",
        "compute_qpi_1d_fft",
        "compute_pr_qpi_volume",
        "compute_real_phase_pll",
        "build_fft_q0_gaussian_notch_1d_discrete",
        "real_phase_lockin",
        "run_qpi_fft",
        "run_qpi_symmetry",
        "symmetrize_qpi",
    }:
        qpi = import_module(".qpi", __name__)
        return getattr(qpi, name)
    if name in {"build_fft_roi_mask", "run_fft_filter"}:
        fft_filter = import_module(".fft_filter", __name__)
        return getattr(fft_filter, name)
    if name in {
        "LFDriftCorrector",
        "apply_lf_displacement_to_stack",
        "compute_lf_drift_field_from_phases",
        "estimate_lf_displacement",
        "estimate_lf_displacement_from_q_vectors",
        "identity_lf_corr_coords",
        "lf_q_vector_from_fft_pixel",
    }:
        topography = import_module(".topography", __name__)
        return getattr(topography, name)
    if name in {"PeakFitResult", "UniversalVortexFitterEngine", "run_multipeak_fit"}:
        multipeak = import_module(".multipeak", __name__)
        return getattr(multipeak, name)
    if name in {
        "build_linear_resample_matrix",
        "build_pinv_operator",
        "compute_r2_score",
        "nanmean_cube_over_pixels",
        "run_sis_didv_deconvolution",
    }:
        deconvolution = import_module(".deconvolution", __name__)
        return getattr(deconvolution, name)
    if name in {"build_qpi_r90_contrast", "build_qpi_spin_contrast", "process_didv_contrast", "sample_linecut"}:
        spstm = import_module(".spstm", __name__)
        return getattr(spstm, name)
    if name in {"apply_waterfall_baseline", "run_waterfall_fit"}:
        waterfall = import_module(".waterfall", __name__)
        return getattr(waterfall, name)
    if name in {"q_cycles_to_pysidam_px_yx", "run_lockin_phase", "run_pysidam_lockin"}:
        phase_lockin = import_module(".phase_lockin", __name__)
        return getattr(phase_lockin, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
