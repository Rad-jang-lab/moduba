# DICOM Batch Pixel Executor

- 목적: execution plan task를 실제 DICOM pixel data 기반으로 실행
- 데이터 흐름: execution plan -> DICOM load -> ROI resolve -> existing analysis function -> raw_result_payload -> execution result
- pydicom 정책: lazy import, 새 dependency 추가 없음, import 실패 시 clear error
- 지원 analysis_type: snr, cnr, uniformity, mtf
- failure: missing path, unreadable dicom, pixel read failure, missing roi, unsupported type, analysis error
- 비목표: 새 계산식 없음, ROI resolver 변경 없음, automatic ROI detection 없음, schema 변경 없음, Window B 대규모 재설계 없음, messagebox 없음


- 24회차부터 기본 analysis_dispatcher가 연결되어 pixel executor는 pixel load/cache + dispatcher 호출을 담당합니다.


## Real DICOM smoke (26회차)
- 25회차 injected loader smoke와 별도로 pydicom-backed real DICOM read path를 테스트한다.
- 목표는 계산 정확도 검증이 아니라 read-path/workflow 연결 smoke-regression이다.


- Window B Batch 탭에 Validate ROI Roles(preflight report) 버튼을 추가해 pixel run 전 입력 품질을 점검할 수 있습니다.
