# DICOM Batch Manifest Foundation (30회차-A)
- 목적: DICOM batch analysis 실행 전에 입력 파일/폴더를 안전하게 수집/검증/요약하는 preparation layer를 제공합니다.
- 이 산출물은 manifest이며, 아직 SNR/CNR/Uniformity/MTF batch 계산을 실행하지 않습니다.

## Manifest Schema
- `dicom_batch_manifest_schema_version: 1`
- `manifest_id`, `generated_at`(timezone-aware ISO), `metadata`, `source_paths`, `recursive`
- `item_count`, `valid_item_count`, `invalid_item_count`, `items[]`

## Item Schema
- `batch_item_schema_version: 1`, `item_id`, `path`, `status(valid|invalid)`, `reason`, `dicom_metadata`
- `dicom_metadata` 범위: PatientID, Study/Series/SOP UID, Modality, StudyDate, SeriesDescription, Rows, Columns, PixelSpacing

## Metadata Extraction Policy
- `pydicom.dcmread(..., stop_before_pixels=True)`로 pixel data는 읽지 않습니다.
- 파일 없음/비DICOM/읽기 실패는 `status=invalid`와 `reason`으로 기록합니다.
- DICOM 파일 수정/저장은 하지 않습니다.

## Export/Viewer Policy
- JSON: `ensure_ascii=False`, `indent=2`, `sort_keys=True`, `allow_nan=False`
- CSV: item-flat schema + `lineterminator="\n"`
- viewer는 Toplevel+Text 기반 preview만 제공

## Scope Boundaries
- DICOM batch execution, ROI preset/automatic ROI, phantom workflow, batch QC 자동 생성은 후속 단계입니다.
- 계산 로직/normalized result/reference validation은 변경하지 않았습니다.

## Privacy Note
- anonymization은 이번 단계 범위가 아니며, manifest에는 위 metadata만 저장합니다.

- DICOM batch manifest는 파일/metadata 입력 레이어이고 ROI preset은 이미지별 ROI 정의 레이어입니다.
- 30-B에서는 manifest와 preset을 자동 결합하지 않습니다.

- manifest는 input/metadata 레이어, plan은 manifest+roi preset readiness 판단 레이어입니다.

- manifest metadata Rows/Columns는 ROI bounds validation 입력으로 사용될 수 있으며 pixel data는 여전히 읽지 않습니다.
- manifest는 execution plan의 원천 item metadata layer이며, execution plan 단계에서도 pixel data는 읽지 않습니다.
