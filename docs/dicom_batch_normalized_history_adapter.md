# DICOM Normalized Execution → History Adapter

- 목적: normalized execution result를 analysis history record로 변환하는 foundation 제공.
- 관계: normalized execution result 자체는 history record가 아니며 adapter를 통해 변환됩니다.
- 정책: item 1개당 history record 1개 생성(단, normalized task가 하나도 없으면 record 미생성).

## Task 처리
- `normalized` task: history results에 포함.
- `skipped` task: results 제외, metadata.skipped_tasks 보존.
- `error` task: results 제외, metadata.error_tasks 보존.
- unknown status: ValueError.

## Metadata
- history_source, normalization_id, source_run_id, normalized_generated_at, item_id, dicom_path
- task/normalized/skipped/error count
- skipped_tasks, error_tasks
- roi_ids_by_analysis, normalization_status_by_analysis

## Record ID
- `{record_id_prefix or 'normalized_batch'}_{normalization_id}_{item_id}`

## JSONL append
- analysis_history_store append helper를 재사용.
- 입력 records 순서 유지, 입력 mutate 없음.

## Viewer helper scope
- current_normalized_dicom_batch_execution_result 우선 사용.
- 필요 시 build 단계에서만 current_dicom_batch_execution_result→normalized fallback 허용.

## Non-goals
- batch QC run 자동 생성 없음.
- report 자동 생성 없음.
- real viewer calculation adapter 구현 없음.
- 계산 로직/ROI resolver 변경 없음.
- DICOM pixel read 없음.


- 생성된 history records는 후속 normalized Batch QC adapter를 통해 Batch QC run으로 연결할 수 있습니다.
- 단, history adapter 자체는 Batch QC run을 자동 생성하지 않습니다.

- Window B Batch 탭에서 normalized workflow action을 명시적으로 호출해 실행할 수 있습니다.
