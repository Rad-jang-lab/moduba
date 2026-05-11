# DICOM Batch Execution Result Normalization Foundation

- 목적: batch execution의 `raw_result_payload`를 analysis result normalized model로 변환하는 독립 레이어를 제공.
- execution result는 원본(raw) 보존 레이어, normalized execution result는 표시/후속 adapter 친화 레이어.

## 정책
- completed: `normalize_analysis_result(analysis_type, raw_result_payload)` 재사용.
- blocked: `normalization_status=skipped`, `skip_reason=blocked`.
- not_executed: `normalization_status=skipped`, `skip_reason=not_executed`.
- error: `normalization_status=error`, 원본 error 보존.
- completed + payload None 또는 normalize 실패(ValueError): `normalization_status=error`.
- unknown status: ValueError.

## Schema
- top-level: `dicom_batch_execution_normalization_schema_version=1`, counts, source_run_id, items.
- item: `batch_item_normalization_schema_version=1`, item_id, dicom_path, task_normalizations.
- task: `batch_task_normalization_schema_version=1`, analysis_type, source_task_status, normalization_status, roi_ids, skip_reason, error, normalized_result.

## MTF curve
- normalized_result의 `curves.mtf`를 그대로 사용(analysis_result_model 정책 재사용).

## Export/Preview
- JSON: deterministic (`ensure_ascii=False`, `indent=2`, `sort_keys=True`, `allow_nan=False`).
- CSV: task row flat export, metric/curve 이름 요약 컬럼 포함.
- viewer preview: Toplevel+Text 최소 표시.

## 범위 명시
- history record 자동 생성 없음.
- batch QC run 자동 생성 없음.
- report 자동 생성 없음.
- real viewer calculation adapter 구현 없음.
- 계산 로직 변경 없음.
- ROI resolver 변경 없음.


- normalized execution result는 history adapter를 통해 history records로 변환될 수 있습니다.
- 단, normalization 단계 자체는 history records를 자동 생성하지 않습니다.


- 흐름: execution result → normalized execution result → history records → Batch QC run.
- normalization 단계 자체는 history/QC/report를 자동 생성하지 않습니다.


- 흐름: execution result → normalized execution result → history records → Batch QC run → report/export.
- normalization 단계 자체는 report/export를 자동 생성하지 않습니다.

- Window B Batch 탭에서 normalized workflow action을 명시적으로 호출해 실행할 수 있습니다.
