# DICOM Batch Real DICOM Smoke

## 목적
25회차의 injected `pixel_loader` smoke를 보완해, 26회차에서는 실제 `pydicom` 기반 `dcmread -> pixel_array` 경로가 batch workflow에 연결되는지 검증한다.

## Fixture 정책
- 테스트 중 임시 디렉터리에 synthetic DICOM만 생성
- PHI/임상 데이터 사용 금지
- uncompressed transfer syntax 사용
- 작은 deterministic pixel array 사용

## pydicom 정책
- 애플리케이션 모듈 top-level `import pydicom` 금지
- lazy import 유지
- dependency 추가 없음
- pydicom unavailable 경로는 clear error로 검증

## Smoke 범위
DICOM read -> pixel_array -> pixel executor -> dispatcher -> execution result -> history -> Batch QC run -> report export

## 비목표
계산식 변경, ROI resolver 변경, schema 변경, 대규모 UI 변경, messagebox 추가는 범위 밖.
