# Analysis Batch QC Foundation (29회차-A)
- history records를 batch item으로 묶어 batch QC run을 생성하는 foundation입니다.
- threshold_config는 optional이며 명시 전달된 경우에만 item별 평가를 수행합니다.
- current_threshold_config/catalog selected config는 자동 사용하지 않습니다.
- JSON/CSV export를 제공하며 MTF curve raw data는 summary text/CSV에 덤프하지 않습니다.
- viewer는 Toplevel+Text 기반 batch summary viewer만 제공합니다.
- DICOM batch execution/ROI preset/automatic ROI/batch DICOM analysis는 후속 단계입니다.
- 계산 로직은 변경하지 않았습니다.

## 29-B Selected Threshold Batch UX Wrapper
- 기본 batch QC method는 `current_threshold_config`를 자동 사용하지 않습니다.
- `use_selected_threshold_config=True` 또는 selected-threshold 전용 wrapper 호출 시에만 `current_threshold_config`를 사용합니다.
- `threshold_config` 인자를 명시 전달하면 selected config보다 항상 우선합니다.
- `catalog.selected_config_id`는 batch QC에 자동 사용되지 않습니다.
- catalog 선택 config를 batch QC에 적용하려면 먼저 **Apply Selected to Viewer**로 `current_threshold_config`에 반영한 뒤 selected-threshold wrapper를 호출해야 합니다.
- selected-threshold wrapper는 config 선택 UX helper이며 threshold evaluation engine/계산 로직을 변경하지 않습니다.
- JSON/CSV batch export schema는 변경하지 않고 threshold_evaluation 포함 여부만 선택 정책에 따라 달라집니다.
- DICOM batch execution/ROI preset/automatic ROI/batch DICOM analysis는 여전히 후속 단계입니다.

- 30-A DICOM batch manifest는 history-record 기반 Batch QC와 별개인 입력 준비 레이어입니다.
- DICOM manifest 자체는 batch QC run을 생성하지 않으며, 후속 ROI/analysis execution 이후 history/batch QC와 연결됩니다.

- Batch QC는 history 결과 묶음 레이어이며 ROI preset은 향후 DICOM batch execution 준비 입력 레이어입니다.
- ROI preset 자체는 batch QC run을 생성하지 않습니다.

- DICOM batch plan은 실행 전 입력 계획 레이어이며 Batch QC는 실행 후 history 결과 레이어입니다.

- ROI bounds validation은 execution 전 준비 layer이며 Batch QC는 execution 후 history 결과 layer입니다.
- execution plan은 실행 전 dry-run layer이며 Batch QC run을 자동 생성하지 않습니다.

- batch execution result는 아직 batch QC run을 자동 생성하지 않으며, 후속 단계에서 execution result → history records → batch QC 연결이 가능합니다.



## Raw Export vs Report Export
- `analysis_batch_qc.py`의 JSON/CSV export는 batch_qc_run 원본(raw) 출력입니다.
- `analysis_batch_qc_report.py`의 text/PDF export는 사람이 읽기 쉬운 report model 출력입니다.
