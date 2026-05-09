# DICOM Batch History Adapter

## 목적
DICOM batch execution result를 normalized analysis history records 및 Batch QC run 흐름으로 연결합니다.

## 데이터 흐름
execution result -> task_result -> normalized analysis result -> analysis history record -> Batch QC run

## task status 처리
- completed: `raw_result_payload` dict이면 `normalize_analysis_result` 수행
- completed + payload 없음: invalid 결과(`BATCH_TASK_MISSING_RAW_RESULT_PAYLOAD`)
- blocked/error/not_executed: invalid 결과로 보존
- normalization error: item 전체 중단 없이 invalid 결과로 보존

## 그룹핑
- DICOM item 단위로 history record 1개 생성
- item의 task_results는 analysis_type별 normalized result로 구성
- task_results 비어 있는 item은 record 생성 생략

## metadata 보존
- history_source=dicom_batch_execution_result
- batch_run_id, execution_plan_id, batch_generated_at
- item_id, dicom_path, dicom_status, bounds_status
- task_status_counts, roi_ids_by_analysis

## threshold_config 정책
- 자동 적용 없음
- 명시 전달 또는 selected-threshold viewer wrapper에서만 사용

## 비목표
- DICOM pixel data read 없음
- SNR/CNR/Uniformity/MTF 공식 변경 없음
- ROI resolver 변경 없음
- automatic ROI detection 없음
- execution/history/batch QC schema 변경 없음
- Window B 대규모 UI 변경 없음
