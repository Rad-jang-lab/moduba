# Window B Adapter Dependencies

## 목적
Window B panel factory 내부의 viewer 의존성을 명확히 기록하고, `viewer_adapter` 경계를 고정한다.

이번 단계 원칙:
- 의존성 제거가 아니라 **가시화/경계 고정**
- adapter는 얇은 전달 계층(위임)만 담당
- 기존 UI/동작/callback 의미는 변경하지 않음

## 현재 의존성 목록

| 탭 | 의존 대상 | 사용 이유 | 분류 | 향후 분리 가능성 |
|---|---|---|---|---|
| Analysis | `viewer_adapter.ui_colors["border"]` | 기존 viewer 테마와 동일한 border 유지 | UI refresh / viewport styling | 가능 |
| Analysis | `viewer_adapter._relayout_analysis_result_rows` | canvas 폭 변경 시 기존 결과 행 재배치 콜백 재사용 | UI refresh | 가능 |
| Analysis | `viewer_adapter.export_analysis_results_csv/json` | 기존 export command 경로 유지 | report/export callback | 가능 |
| Analysis | `viewer_adapter.analysis_results_*` 속성 대입 | 기존 refresh 루프가 참조하는 widget 핸들 등록 | legacy compatibility | 가능 |
| History | `viewer_adapter.history_metric_filter_var`, `history_search_var` | 기존 filter/search state var 재사용 | selection/filter state | 가능 |
| History | `viewer_adapter._refresh_result_history_table` | 필터/검색 이벤트에서 기존 targeted refresh 호출 | UI refresh | 가능 |
| History | `viewer_adapter._on_history_row_selected` | row selection callback 의미 유지 | selection callback | 가능 |
| History | `viewer_adapter.delete/clear/copy/export/compare` | 기존 액션 버튼 경로 유지 | history action / report-export callback | 가능 |
| History | `viewer_adapter.result_history_table`, `history_compare_button` 대입 | 기존 비교/선택 복원 루프 호환 | legacy compatibility | 가능 |
| Session | `viewer_adapter.save/load/_reset_analysis_session_state` | 기존 session action 경로 유지 | session callback | 보류 |
| Report | `viewer_adapter.export_*` | 기존 report/export action 경로 유지 | report/export callback | 보류 |

## adapter 원칙
- adapter는 controller가 아니다.
- adapter는 데이터를 가공하지 않는다.
- adapter는 viewer 전체 기능을 대체하지 않는다.
- adapter는 callback/속성을 그대로 전달한다.

현재 `window_b_panel_factory.py`의 `WindowBViewerAdapter` Protocol은 위 최소 인터페이스를 코드로 고정한다.

## 다음 단계 분리 후보
1. Window B 전용 view-state 객체 도입
   - `analysis_results_table`, `result_history_table` 등 viewer 속성 직접 대입 제거.
2. History selection/refresh handler 분리
   - `_on_history_row_selected`, `_refresh_result_history_table`를 Window B 핸들러로 분리.
3. Session/Report action provider 명시화
   - viewer callback 직접 바인딩을 controller action provider로 치환.
4. 창 A 경량화와 함께 제거 가능한 의존성
   - A/B가 공유하는 tk variable를 B 전용 상태로 이동.

## 비고
- 이번 단계는 동작 동일성 우선으로 copy 방식 UI를 유지.
- viewer `_build_*` 메서드는 창 A 호환성 때문에 유지한다.
