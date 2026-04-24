# Window A Legacy Builder Audit

## 목적
창 A 내부 legacy builder의 호출 경로를 검증하고 제거 가능성을 판단한다.

## 검증 대상
- `_build_analysis_results_panel`
- `_build_results_history_panel`

## 호출 경로 분석
| 메서드 | 호출 위치 | 사용 여부 | 판단 | 다음 조치 |
|---|---|---|---|---|
| `_build_analysis_results_panel` | `dicom_viewer.py::_build_signal_analysis_toolbar`에서 1회 직접 호출 | 사용 중 | 창 A 전용 유지 | 창 A 분석 실행 UI 축소 단계에서 호출 제거 여부 재평가 |
| `_build_results_history_panel` | 코드베이스 직접 호출 없음(정의만 존재) | 사실상 미사용 | Deprecated + 제거 후보 | 제거 전 조건 충족 여부를 다음 단계에서 재검증 후 삭제 검토 |

## 세부 검증 메모
- 창 B: `window_b_manager.py`는 panel factory 호출만 사용하며 legacy builder 호출 없음.
- panel factory: `window_b_panel_factory.py`는 독립 복제 UI로 구성됨.
- 테스트: legacy builder를 직접 호출하는 테스트 없음(문자열 기반 비호출 검증만 존재).
- 동적 호출(getattr/문자열 dispatch) 확인: 검색 기준으로 발견되지 않음.

## 제거 전 조건
- 창 A에서 호출 없음
- 창 B에서 호출 없음
- 테스트에서 호출 없음
- 동일 기능이 panel factory에 존재
- 기존 테스트 통과

## 다음 단계
- `_build_results_history_panel`은 deprecated 상태 유지.
- 창 A 분석 UI 정리 단계에서 `_build_analysis_results_panel` 호출 제거 가능성 재검토.
- 두 메서드 모두 삭제는 다음 단계에서 별도 PR로 수행.
