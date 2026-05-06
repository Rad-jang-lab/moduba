# IQA Testing Matrix

## 1) 테스트 파일별 목적
- `tests/test_iqa_metrics.py`: metric 정확성, 수치 안정성.
- `tests/test_iqa_result_schema.py`: IQAResult/Context/JSON-safe 변환.
- `tests/test_iqa_dicom_adapter.py`: DICOM mode 분기, photometric, ROI adapter.
- `tests/test_iqa_export_schema.py`: analysis/export flat schema.
- `tests/test_iqa_display.py`: 표시 섹션/라벨/warning mapping/정렬.
- `tests/test_iqa_ui_state.py`: state/readiness 정책.
- `tests/test_iqa_ui_wiring.py`: viewer 실행/invalid/ROI/warning wiring.
- `tests/test_iqa_histogram.py`: range/normalize/distribution hint.
- `tests/test_iqa_history.py`: success/invalid history, stale 방지.
- `tests/test_iqa_report.py`: single/invalid/history-summary report.
- `tests/test_iqa_report_export.py`: TXT/JSON/CSV payload/bundle 안전성.
- `tests/test_iqa_report_file_export.py`: 파일 writer(TXT/JSON/CSV) 및 no UI dependency.
- `tests/test_iqa_report_export_ui.py`: export UI helper의 format/resolve/save/status pure test.
- `tests/test_iqa_report_ui_export.py`: viewer export UI callback 회귀(no messagebox, cancel/failure 등).

## 2) 보장 정책
- uint overflow 및 수치 경계 처리
- data_range policy 보장
- DICOM mode separation
- ROI no silent fallback
- warning mapping/dedup/severity
- histogram root context
- session restore no auto-recompute
- report JSON-safe
- file writer no UI dependency
- export UI no messagebox

## 3) 회귀 실행 명령
- `python -m py_compile dicom_viewer.py iqa_report_export_ui.py iqa_report_file_export.py iqa_report_export.py iqa_report.py iqa_history.py iqa_display.py`
- `pytest -q`
- 부분 테스트:
  - `pytest -q tests/test_iqa_report_export_ui.py tests/test_iqa_report_ui_export.py`

## 4) 현재 baseline
- `pytest`: **177 passed**
- warnings: **0**

## 5) 향후 테스트 추가 원칙
- 계산 로직은 pure helper 테스트 우선.
- UI는 monkeypatch 가능한 wrapper 기반 테스트.
- messagebox 사용 금지.
- warnings 숨기기 금지.
- payload schema 변경 시 export/history/session/report 테스트 동시 보강.
