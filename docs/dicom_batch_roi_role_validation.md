# DICOM Batch ROI Role Validation

- 목적: batch 실행 전 ROI preset/task role mapping preflight 검증.
- 입력: ROI preset, execution plan task roi_ids, optional bounds validation result.
- 출력: execution/history/QC/report schema와 독립적인 validation report.
- analysis_type 정책: snr/cnr 최소 2개 roi_ids, uniformity/mtf 최소 1개 roi_ids.
- role metadata가 없으면 roi_ids 존재/개수 기반 검증으로 동작.
- unknown/missing/duplicate ROI와 unsupported analysis_type를 reason code로 보고.
- strict 정책: 기본 자동 block 없음, 명시적 strict mode에서만 block.
- 비목표: ROI resolver 변경/자동 ROI 추론/계산 공식 변경/DICOM read/UI 대규모 변경/messagebox 추가 없음.
