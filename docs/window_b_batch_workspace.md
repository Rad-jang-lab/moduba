# Window B Batch Workspace

## 목적
DICOM batch execution result를 Window B에서 history/QC 흐름으로 연결합니다.

## UI 구성
- Summary: 현재 execution result 및 bridge/QC 상태
- Actions: preview/build/append/build QC
- Preview: batch workspace 요약 및 bridge 미리보기 텍스트

## 지원 동작
- Bridge preview
- Build history records
- Append JSONL history
- Build Batch QC run

## threshold 정책
- 자동 적용 없음
- explicit threshold_config 우선
- selected threshold config는 옵션 True일 때만 사용

## 비목표
- 계산 공식 변경 없음
- ROI resolver 변경 없음
- DICOM pixel data read 없음
- schema 변경 없음
- Window B 대규모 재설계 없음


## Batch QC Report / Export
- Preview Batch QC Report
- Export Batch QC JSON
- Export Batch QC CSV
- Export Batch QC Text
- Export Batch QC PDF
- Preview 영역은 bridge/report/export 결과와 에러/취소 상태를 공통 텍스트로 표시합니다.


## Batch Execution Plan / Run
- Build Execution Plan
- Run Batch Execution
- Preview Execution Result
- 실행 결과는 기존 bridge/history/QC/report/export 흐름으로 이어집니다.


- Check Pixel Executor
- Run Pixel Batch Execution
- Run Batch Execution은 주입형 executor/None 정책, Run Pixel Batch Execution은 pixel-backed executor를 사용합니다.


- Check Pixel Executor는 pixel loader + dispatcher readiness를 함께 표시합니다.
- Run Pixel Batch Execution은 기본 viewer dispatcher를 사용합니다.


## Real DICOM smoke (26회차)
- 25회차 injected loader smoke와 별도로 pydicom-backed real DICOM read path를 테스트한다.
- 목표는 계산 정확도 검증이 아니라 read-path/workflow 연결 smoke-regression이다.


- Window B Batch 탭에 Validate ROI Roles(preflight report) 버튼을 추가해 pixel run 전 입력 품질을 점검할 수 있습니다.

- Window B Batch 탭에서 normalized workflow action을 명시적으로 호출해 실행할 수 있습니다.
