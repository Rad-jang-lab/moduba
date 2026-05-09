# DICOM Batch Analysis Dispatcher

- 목적: 기존 단일 이미지 분석 로직을 batch pixel executor dispatcher로 연결
- 데이터 흐름: task/item/context -> pixel_array -> roi_ids/resolved rois -> existing analyzer callable -> raw_result_payload -> normalize compatibility
- 지원 analysis_type: snr, cnr, uniformity, mtf
- analyzer injection: snr_analyzer, cnr_analyzer, uniformity_analyzer, mtf_analyzer
- viewer default dispatcher: viewer wrapper가 기본 analyzer들을 연결
- payload validation: normalize_analysis_result dry-run으로 호환성 검증
- failure: missing analyzer, missing analysis_type, missing roi, invalid payload, unsupported analysis_type
- 비목표: 새 계산식 없음, ROI resolver 변경 없음, automatic ROI detection 없음, DICOM pixel load 없음, schema 변경 없음, Window B 대규모 재설계 없음, messagebox 없음


- Window B Batch 탭에 Validate ROI Roles(preflight report) 버튼을 추가해 pixel run 전 입력 품질을 점검할 수 있습니다.
