# UI Responsibility Boundary

## 목적
창 A(Viewer)와 창 B(Window B)의 역할을 명확히 분리하기 위한 기준을 정의한다.

이번 단계 원칙:
- 기능/동작 변경 없이 책임 경계만 문서화
- 창 A: 입력/인터랙션/시각화 중심
- 창 B: 분석/결과/기록/세션/리포트 중심

## 현재 UI 구성 분석

### 창 A (Viewer)

| UI 요소 | 현재 기능 | 분류 | 판단 근거 |
|---|---|---|---|
| HOME 탭 `Open Window B` 버튼 | 창 B 작업 공간 진입 | 유지 | 창 A에서 창 B 호출을 위한 최소 진입점이며 작업 위임 트리거 역할 |
| IMAGE 탭 `Save Session` / `Load Session` 버튼 | 창 B를 열고 refresh 후 세션 저장/로드 실행 | 위임 | 세션 관리 본 업무는 창 B 책임이며 창 A는 진입점/위임만 수행 |
| MEASURE 탭(도구, 그리드, ROI/Line 관리) | ROI/Line 입력, 선택/삭제, overlay/측정 조작 | 유지 | 영상/측정 인터랙션은 창 A 본래 책임 |
| ANALYSIS 탭 `Signal Analysis` 영역(SNR/CNR/Uniformity/MTF 실행 UI) | 분석 실행 입력/트리거 | 유지(중기), 제거 후보(장기) | 현재는 창 A에서 분석 실행 트리거를 제공하나 결과/기록은 B가 주 공간 |
| ANALYSIS 탭 `Image Analysis` 영역(SSIM/PSNR/MSE/HIST) | 이미지 분석 실행 트리거 | 유지(중기), 제거 후보(장기) | 실행 입력은 남아 있으나 결과 소비/관리는 B 중심으로 전환 중 |
| ANALYSIS 탭 `Results History` 영역(안내 + Open 버튼) | 창 B 사용 안내 및 진입 | 유지 | 중복 테이블 대신 최소 안내/진입점만 남긴 상태 |
| EXPORT 탭 (이미지/프레임/뷰 스크린샷 등) | viewer 출력 중심 export | 유지 | viewer 시각화 결과물 export는 A 책임에 부합 |
| 창 A 내부 Analysis Results 패널 builder (`_build_analysis_results_panel`) | 기존 결과 패널 빌더(현재 A에서 직접 주작업 공간으로 사용하지 않음) | 제거 후보 | 창 B panel factory가 동일 역할을 수행하므로 중복성 존재 |
| 창 A 내부 Results History 패널 builder (`_build_results_history_panel`) | 기존 history 패널 빌더(현재 A history 탭에서 직접 사용하지 않음) | 제거 후보 | 창 B history 패널이 주작업 공간이므로 A 중복 빌더는 장기적으로 정리 가능 |

### 창 B

| 탭 | 역할 |
|---|---|
| Analysis | 분석 결과 표시 + 결과 export 진입 |
| History | 측정/분석 히스토리 표시/필터/비교/삭제/export |
| Session | 세션 저장/로드/리셋 진입 |
| Report | 분석/히스토리 export 진입 |

## 책임 분리 원칙
- 창 A: 입력 / 인터랙션 / 시각화
- 창 B: 분석 / 결과 / 기록 / 관리

## 위임 정책
- 창 A에서 세션 관리 버튼은 창 B를 열고 refresh 후 실행한다.
- 창 A의 Results History 영역은 안내/진입점만 유지한다.
- 창 A에서 분석 결과/기록의 주 소비 UI는 제공하지 않고 창 B로 유도한다.

## 향후 구조 방향
- 창 A는 “뷰어 + 입력 인터페이스”로 제한
- 창 B는 “분석 작업 공간”으로 고정

## 다음 단계 후보
- 창 A Signal/Image Analysis 실행 UI를 창 B 실행 UI로 이관할지 검토
- 창 A에 남아 있는 `_build_analysis_results_panel` 제거/축소 검토
- 창 A에 남아 있는 `_build_results_history_panel` 제거/축소 검토
- 창 A에는 Open Window B 및 최소 상태 요약만 유지하는 방향 검토

## 비고
- 본 문서는 책임 경계 정의이며, 기능 삭제/코드 제거는 수행하지 않는다.
- Window B panel factory 및 manager 구조는 현행 유지한다.
