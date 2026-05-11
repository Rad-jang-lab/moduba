# Normalized Batch QC Report/Export Adapter

- 목적: normalized Batch QC run을 report model로 변환하고 JSON/CSV/Text/PDF export를 제공.
- Batch QC run schema는 유지, report model은 별도 schema(`normalized_batch_qc_report_schema_version=1`).
- threshold_evaluation이 없으면 `threshold_overall_status=missing`, 있으면 기존 `overall_status` 반영.
- report/export는 명시 호출 시에만 수행.
- Batch QC run 자동 생성 없음.
- real viewer calculation adapter 없음.
- 계산 로직/ROI resolver 변경 없음.
- DICOM pixel read 없음.
- 외부 PDF dependency 추가 없음.

- Window B Batch 탭에서 normalized workflow action을 명시적으로 호출해 실행할 수 있습니다.
