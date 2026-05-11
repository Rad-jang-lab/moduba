# Window B Normalized Batch Workflow

Window B Batch 탭에서 normalized workflow 액션을 명시적으로 호출해 다음 흐름을 수행합니다.

- Build Normalized Execution
- Preview/Export Normalized Execution (JSON/CSV)
- Build/Append Normalized History Records
- Build Normalized Batch QC Run
- Preview/Export Normalized Batch QC Report (JSON/CSV/Text/PDF)

상태 캐시:
- current_normalized_dicom_batch_execution_result
- current_normalized_execution_history_records
- current_batch_qc_run
- current_normalized_batch_qc_report_model

정책:
- selected threshold config는 checkbox(True)일 때만 사용
- export는 명시 버튼 호출 시에만 수행
- dialog cancel은 None/취소 상태로 처리
- messagebox 미사용

Non-goals:
- real viewer calculation adapter
- 계산 로직/ROI resolver 변경
- DICOM pixel read
- schema 변경
- Window B 전체 재설계
