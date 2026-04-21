# 모두바 구현 검증 리포트 (코드 기준)

본 문서는 `dicom_viewer.py` 기준으로 ROI/Grid/Analysis 기능의 구현 상태를 점검한 결과를 기록한다.

- 기준 파일: `dicom_viewer.py`
- 검증 방식: 정적 코드 분석(함수/데이터 흐름 확인)
- 실행 검증: UI 수동 테스트 미실시

## 핵심 관찰

- ROI/라인/폴리곤 측정 및 통계, SNR/CNR, 라인 프로파일, 측정 데이터 구조화(메타/세트 JSON/CSV)는 구현되어 있다.
- Uniformity 계산은 구현되어 있지 않다.
- ROI 역할(role) 영구 저장은 제거되었고 입력 슬롯 기반 선택으로 대체되었다.
- Pixel Spacing은 `PixelSpacing`→`ImagerPixelSpacing` 순으로 읽고, 비정상 값은 `None`으로 처리해 px 기반으로 안전 폴백한다.
- 좌표계는 화면-이미지 변환 함수를 분리해 확대/이동/리사이즈 시 재렌더링하도록 구성되어 있다.

## 즉시 리스크

1) `select_roi_from_grid`의 `x1/y1` 클리핑 상한이 `width-1/height-1`라 경계 ROI가 1px 작아질 수 있음.
2) `_roi_stats`는 ROI를 `ymax+1`, `xmax+1`로 포함 구간 계산하여 `compute_measurement`(배타 경계)와 면적 정의가 다름.
3) 역할 기반 워크플로우 요구 대비 `assign_roi_role`는 안내 메시지만 남아 있음.
4) 라인 프로파일 거리 단위가 px 고정(Spacing mm 반영 없음).
5) Uniformity 계산 기능 부재.
