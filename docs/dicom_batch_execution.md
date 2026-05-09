# DICOM Batch Execution Foundation (32-A)

- 목적: execution plan(dry-run)을 기반으로 task 실행 결과를 기록하는 실제 실행 foundation을 도입합니다.
- 관계: execution plan은 실행 대상/차단 사유 목록, execution result는 executor 호출 결과(completed/error/not_executed/blocked) 기록 레이어입니다.
- ROI 정책: roi_preset의 `roi_id`로 task `roi_ids`를 resolve하며 ROI resolver 자체는 변경하지 않습니다.
- executor 정책: `analysis_executor(dicom_path, analysis_type, roi_definitions, task)` 주입형.
  - blocked task: 실행하지 않음
  - executable + executor 없음: `not_executed`
  - executable + executor 성공: `completed`
  - executor 예외: `error`
- task result schema: `batch_task_execution_result_schema_version: 1`, `analysis_type`, `status`, `dicom_path`, `roi_ids`, `blocked_reasons`, `raw_result_payload`, `error`.
- batch result schema: `dicom_batch_execution_result_schema_version: 1`, `run_id`, `generated_at`, count fields, `items[].task_results`.
- export: JSON(정렬/indent), CSV(item-task flat).
- viewer: preview/export helper만 제공(Toplevel+Text), 자동 실행 UX/대규모 UI 변경 없음.
- 비범위: automatic ROI detection 미구현, ROI resolver 변경 없음, SNR/CNR/Uniformity/MTF 공식 변경 없음.
- 비범위: normalized result/history/batch QC 자동 연결 없음(후속 adapter 단계에서 연결 예정).
