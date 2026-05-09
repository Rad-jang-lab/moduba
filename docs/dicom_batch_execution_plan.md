# DICOM Batch Execution Plan (31-B)

## Why
- 실행 전에 어떤 분석 task가 실제 실행 가능(executable)한지, 어떤 이유로 차단(blocked)되는지 dry-run으로 고정/가시화하기 위해 도입되었습니다.

## Relationship
- manifest: item metadata source layer
- ROI preset: role/roi definition layer
- batch analysis plan: role completeness readiness layer
- ROI bounds validation: image bounds readiness layer
- execution plan: batch plan + bounds validation 결합 결과(dry-run task list)

## Schema
- execution plan schema: `dicom_batch_execution_plan_schema_version: 1`
- execution item schema: `execution_item_schema_version: 1`
- execution task schema: `execution_task_schema_version: 1`

## Policy
- executable/blocked 정책:
  - task별 blocked reason 집합이 비어 있으면 executable
  - item은 하나 이상의 executable task가 있으면 executable item
- blocked reason 정책:
  - `dicom_invalid`
  - `bounds_not_evaluated`
  - `roi_out_of_bounds`
  - `readiness_mismatch`
  - `missing_required_roles`
- ROI role → ROI id mapping:
  - analysis type별 role map을 기준으로 `roi_results[].analysis_roles`를 매칭해 `roi_ids`를 생성
- export 정책:
  - JSON: deterministic 정렬/indent 출력
  - CSV: item-task flatten row 출력

## Viewer/runtime cache integration (31-B2)
- runtime cache:
  - `current_dicom_batch_analysis_plan`
  - `current_roi_bounds_validation`
  - `current_dicom_batch_execution_plan`
- method 인자 우선순위:
  - 명시 인자가 있으면 인자 우선
  - 인자가 없으면 current cache 사용
- dialog cancel 정책:
  - save dialog 취소 시 `None` 반환, cache mutation 없음
- preview/export 의미:
  - dry-run 실행 계획 확인용이며 actual execution 아님

## Out of scope (still deferred)
- DICOM batch analysis actual execution
- SNR/CNR/Uniformity/MTF batch calculation execution
- DICOM pixel data read / `dcmread` 호출
- ROI resolver 변경 / automatic ROI detection
- physical unit/pixel-spacing validation
- MTF edge orientation validation

- execution plan은 dry-run task list이고, execution result는 executor를 통해 task별 결과를 기록하는 후속 layer입니다.
