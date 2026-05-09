from ui_display_helpers import (
    build_analysis_display_model,
    build_pair_status_label,
    build_viewer_a_status_label,
    format_compact_path_label,
)


def test_compact_path_parent_and_basename():
    assert format_compact_path_label('/tmp/folder_A/image001.dcm') == 'folder_A/image001.dcm'


def test_same_basename_different_directory_are_distinct():
    a = format_compact_path_label('/tmp/folder_A/image001.dcm')
    b = format_compact_path_label('/tmp/folder_B/image001.dcm')
    assert a != b


def test_long_path_uses_ellipsis_and_preserves_tail():
    got = format_compact_path_label('/tmp/very_long_parent_folder_name/image001_with_long_name.dcm', max_chars=24)
    assert got.startswith('...')
    assert 'image001_with_long_name.dcm'[-8:] in got


def test_none_or_empty_path_safe_placeholder():
    assert format_compact_path_label('') == 'No file'
    assert format_compact_path_label('   ') == 'No file'


def test_windows_and_posix_paths():
    assert format_compact_path_label(r'C:\data\folder_A\image001.dcm') == 'folder_A/image001.dcm'
    assert format_compact_path_label('/data/folder_A/image001.dcm') == 'folder_A/image001.dcm'


def test_unicode_and_space_filename():
    got = format_compact_path_label('/tmp/긴 폴더/긴 파일 명.dcm')
    assert got == '긴 폴더/긴 파일 명.dcm'


def test_viewer_a_status_label_format_and_1_based_frame():
    got = build_viewer_a_status_label('/tmp/folder_A/image001.dcm', current_frame_index=0, frame_count=120)
    assert got == 'A | folder_A/image001.dcm | Frame 1/120'


def test_viewer_a_status_label_without_path_or_frames():
    got = build_viewer_a_status_label('', current_frame_index=0, frame_count=0)
    assert got == 'A | No file | Frame -'


def test_pair_status_compact_labels_and_scope_roi():
    got = build_pair_status_label('/tmp/folder_A/image001.dcm', '/tmp/folder_B/image001.dcm', '실행 가능', roi_label='ROI 1', scope='roi')
    assert 'Reference=folder_A/image001.dcm' in got
    assert 'Target=folder_B/image001.dcm' in got
    assert 'ROI=ROI 1' in got


def test_display_model_for_snr_valid_result():
    normalized = {"analysis_type": "snr", "status": "success", "validity": "valid", "metrics": {"snr": 2.5}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}}
    out = build_analysis_display_model(normalized)
    assert out["title"] == "SNR"
    assert out["metric_rows"][0]["name"] == "snr"


def test_display_model_for_mtf_valid_result_with_curve_summary():
    normalized = {
        "analysis_type": "mtf",
        "status": "ok",
        "validity": "valid",
        "metrics": {"mtf50": 0.2},
        "curves": {"mtf": {"x": [0.0, 0.1], "y": [1.0, 0.8]}},
        "warnings": [],
        "reason_codes": [],
        "roi_info": {},
    }
    out = build_analysis_display_model(normalized)
    assert out["curve_summaries"][0]["point_count"] == 2


def test_display_model_for_invalid_result_preserves_warnings_and_reasons():
    normalized = {"analysis_type": "mtf", "status": "reject", "validity": "invalid", "metrics": {}, "curves": {}, "warnings": ["w1"], "reason_codes": ["r1"], "roi_info": {}}
    out = build_analysis_display_model(normalized)
    assert out["warning_lines"] == ["w1"]
    assert out["reason_lines"] == ["r1"]
