# ROI Preset Foundation (30회차-B)
- ROI preset은 분석 실행 전 ROI 정의를 저장/검증/재사용하는 입력 정의 레이어입니다.
- 이번 단계는 preset foundation만 제공하며 ROI resolver/automatic ROI/DICOM batch execution은 변경하지 않습니다.

## Schema
- `roi_preset_schema_version: 1`, `name`, `description`, `metadata`, `roi_definitions[]`
- ROI definition: `roi_id`, `label`, `roi_type`, `coordinates`, `analysis_roles`, `notes`

## Supported roi_type
- rectangle, ellipse, polygon, point, line

## Coordinate schema
- rectangle/ellipse: `{x, y, width, height}` finite numeric
- point: `{x, y}` finite numeric
- polygon: `{points:[{x,y}, ...]}` 최소 3점
- line: `{points:[{x,y}, ...]}` 최소 2점

## Supported analysis_roles
- signal, noise, background, region_a, region_b, uniformity, mtf_edge

## Readiness mapping
- SNR: signal + noise
- CNR: region_a + region_b + (noise or background)
- Uniformity: uniformity
- MTF: mtf_edge

## I/O / Viewer policy
- JSON save/load: ensure_ascii=False, indent=2, sort_keys=True
- viewer는 `current_roi_preset`에 보관하고 Toplevel+Text preview 제공
- preset은 image array/pixel data를 포함하지 않음

## Scope boundaries
- ROI resolver 변경 없음
- automatic ROI detection 미구현
- DICOM batch execution 미구현
- 계산 로직 변경 없음

- ROI preset은 batch plan에서 analysis role completeness check에 사용되며 bounds validation은 후속 단계입니다.

- ROI preset coordinate schema는 31-A bounds validation에서 사용됩니다.
- ROI preset의 role/roi_id 정보는 execution task의 `roi_ids` 산출에 사용될 수 있으며 ROI resolver 자체는 변경하지 않았습니다.

- execution result는 roi_id 기반으로 ROI definition을 resolve하지만 ROI resolver 자체는 변경하지 않습니다.
