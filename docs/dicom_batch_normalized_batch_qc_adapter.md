# Normalized History → Batch QC Adapter

- normalized execution history records를 Batch QC run으로 변환하는 adapter.
- convenience path는 normalized execution result를 받아도 내부에서 history adapter를 반드시 경유.
- threshold_config는 기본 자동 적용하지 않음.
- explicit threshold_config만 적용.
- viewer selected threshold는 `use_selected_threshold_config=True`일 때만 사용.
- records empty면 `ValueError("history records are empty")`.
- report/export 자동 생성 없음.
- real viewer calculation adapter 없음.
- 계산 로직/ROI resolver 변경 없음.
- DICOM pixel read 없음.
- schema 변경 없음.


- Batch QC run은 후속 report/export adapter로 연결할 수 있습니다.
- 단, Batch QC adapter 자체는 report/export를 자동 생성하지 않습니다.

- Window B Batch 탭에서 normalized workflow action을 명시적으로 호출해 실행할 수 있습니다.
