# DICOM Batch Run Orchestration

## 목적
Window B에서 execution plan build/run 흐름을 제공합니다.

## 데이터 흐름
manifest / ROI preset / bounds -> execution plan -> injectable analysis_executor -> execution result -> bridge/history/QC/report/export

## analysis_executor 정책
- callable injection
- 테스트는 fake executor 사용
- 이번 회차는 pixel-backed executor 미구현

## task status 정책
- completed
- blocked
- error
- not_executed

## 비목표
- 계산 공식 변경 없음
- ROI resolver 변경 없음
- DICOM pixel data read 없음
- schema 변경 없음
- Window B 대규모 재설계 없음
- messagebox 추가 없음


- Window B에서 Check Pixel Executor / Run Pixel Batch Execution으로 pixel-backed run을 트리거할 수 있습니다.


- Check Pixel Executor preview는 dispatcher readiness까지 포함합니다.


## Real DICOM smoke (26회차)
- 25회차 injected loader smoke와 별도로 pydicom-backed real DICOM read path를 테스트한다.
- 목표는 계산 정확도 검증이 아니라 read-path/workflow 연결 smoke-regression이다.


- Window B Batch 탭에 Validate ROI Roles(preflight report) 버튼을 추가해 pixel run 전 입력 품질을 점검할 수 있습니다.
