# IQA Architecture

## 1) 시스템 개요
모두바의 IQA는 Reference/Target 영상 비교를 통해 MSE/RMSE/PSNR/SSIM/HIST corr를 계산하고, 계산값만이 아니라 **context/warnings/history/report/export**를 함께 보존합니다. 이는 단순 Image Metrics 문자열 출력에서 벗어나 재현 가능한 비교 워크플로우(세션 복원, 히스토리 추적, 보고서 내보내기)를 제공하기 위함입니다.

## 2) 모듈별 역할
- `iqa_metrics.py`: core metric 계산 및 data_range policy 처리.
- `iqa_result_schema.py`: `IQAMetrics`, `IQAContext`, `IQAResult` + JSON-safe 변환.
- `iqa_dicom_adapter.py`: `raw_dicom_pixel` / `modality_lut` / `windowed_display`, photometric inversion, ROI bbox/mask adapter, DICOM context 구성.
- `iqa_export.py`: `IQAResult -> analysis/export record` 변환(평탄화 필드 포함).
- `iqa_display.py`: Summary / Metrics / Histogram / Context / Warnings 표시 모델, warning mapping/정렬.
- `iqa_ui_state.py`: Reference/Target, input_mode/scope/data_range/photometric, ROI 선택 상태 및 readiness.
- `iqa_histogram.py`: histogram range policy, 정규화, distribution hint, preview text.
- `iqa_history.py`: `IQAHistoryEntry`, success/invalid history, max_items 정책.
- `iqa_report.py`: single/invalid/history-summary report + interpretation rule.
- `iqa_report_export.py`: TXT/JSON/CSV payload 및 bundle 생성.
- `iqa_report_file_export.py`: TXT/JSON/CSV 파일 writer (no UI dependency).
- `iqa_report_export_ui.py`: export format normalization, latest report resolve, save execution, status message helper.
- `iqa_report_ui_export.py`: compatibility shim.
- `dicom_viewer.py`: IQA 실행/표시/저장에 대한 UI wiring.

## 3) 데이터 흐름
`Reference/Target selection`
→ `IQASelectionState`
→ `resolve_iqa_run_state`
→ `DICOM adapter or array fallback`
→ `IQA metrics`
→ `histogram enrichment`
→ `IQAResult`
→ `display model`
→ `export record`
→ `history entry`
→ `session payload`
→ `report payload`
→ `file writer`
→ `report export UI`

## 4) 주요 정책
- data_range policy: auto/bits/actual_union(표시/실행 경로 분리 정책 유지).
- input mode: raw_dicom_pixel / modality_lut / windowed_display.
- photometric inversion: MONOCHROME1 관련 경고/옵션 반영.
- ROI policy: scope=roi에서 ROI 필수, no silent full_image fallback.
- shape mismatch: common crop 기반 비교.
- histogram policy: 정규화 및 distribution hint 제공.
- warning severity: error/caution/info 정렬 및 dedup.
- invalid/stale: invalid에서 stale metric 미표시.
- session restore: no auto-recompute 정책(복원 요약만 표시).
- report export: 진단 정확도 판정이 아닌 영상 품질 비교 지표.

## 5) 설계 원칙
- calculation / display / export / UI 분리.
- 분석 경고 처리에 messagebox 미사용.
- scope=roi에서 조용한 full_image 대체 금지.
- invalid 상태에서 stale metrics 금지.
- DICOM IQA는 진단 정확도 판정이 아니라 image quality comparison.
