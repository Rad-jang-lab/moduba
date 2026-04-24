# MTF Tab UI 구조 조사 메모

## 왜 여기서 시작하면 좋은가
- 현재 코드에서 MTF 탭 UI는 **Window B Analysis > Signal Analysis > MTF** 경로로 고정되어 있다.
- 즉, “원래 UI로 복귀” 이슈를 점검할 때는 Window B 진입점과 Signal 하위 탭 구성을 먼저 보면 영향 범위를 빠르게 좁힐 수 있다.

## 상위 진입 구조
1. 창 A ANALYSIS 탭은 실제 분석 UI를 직접 갖지 않고, Window B 사용 안내/진입만 제공한다.
2. 실제 분석 탭 컨테이너는 `WindowBManager`에서 생성된다.
3. Window B의 Analysis 탭은 `build_window_b_analysis_panel()`을 통해 Signal/Image 분석 노트북을 만들고, Signal UI는 viewer adapter의 `_build_signal_analysis_toolbar()`를 호출한다.

## MTF 탭이 그려지는 위치
- `_build_signal_analysis_toolbar()`에서 SNR/CNR/Uniformity/Line Profile/MTF 하위 탭을 생성한다.
- 여기서 생성된 `mtf_tab`으로 `_build_mtf_analysis_panel(mtf_tab)`이 호출되어 MTF 전용 UI가 조립된다.

## MTF 패널 내부 레이아웃
`_build_mtf_analysis_panel()` 기준으로 좌/우 2열 레이아웃:

- 좌측(입력/요약)
  - Input 그룹
    - 선택 ROI 상태 텍스트
    - Imaging Mode 콤보
    - Operating Mode 콤보
    - `Use Selected ROI as Edge ROI` 버튼
    - `Run MTF Analysis` 버튼(초기 disabled)
    - `Show MTF Details` 버튼
    - Validation summary 텍스트
  - Result Summary 그룹
    - MTF50, MTF10, Nyquist MTF, Edge Angle, Edge SNR, ROI Width/Height, Calculation Validity, IEC Compliance, QA Grade
  - Warnings / Validation 그룹
    - 읽기 전용 Text 위젯

- 우측(곡선 뷰어)
  - Curve Viewer 그룹
    - MTF/ESF/LSF 탭 노트북
    - 각 탭 Canvas(리사이즈 이벤트에서 redraw 예약)
  - Curve Summary 그룹
    - MTF/ESF/LSF 상태 라벨

## 탭 전환/리사이즈 시 동작
- Signal 하위 노트북에서 MTF 탭으로 전환될 때 `_on_signal_analysis_tab_changed()`가 redraw를 예약.
- Curve 노트북 탭 전환, Canvas configure 이벤트도 `_schedule_mtf_graph_redraw()`로 수렴.
- redraw는 즉시 수행이 아니라 `after_idle`로 coalesce 된다.

## “원래 UI 복구” 관점에서 우선 확인할 포인트
1. **진입 경로 확인**: 창 A에서 Window B를 여는 동선이 깨졌는지.
2. **탭 생성 확인**: `_build_signal_analysis_toolbar()`에서 MTF 탭 add 순서/라벨이 변경됐는지.
3. **패널 조립 확인**: `_build_mtf_analysis_panel()` 호출이 제거/조건 분기되었는지.
4. **상태 바인딩 확인**: `signal_analysis_inputs/results` 기본값 키가 MTF UI 위젯과 일치하는지.
5. **redraw 트리거 확인**: MTF 탭 진입/curve 탭 변경 시 redraw 스케줄 경로가 유지되는지.

## 빠른 디버깅 시작 명령 예시
```bash
rg -n "_build_signal_analysis_toolbar|_build_mtf_analysis_panel|_on_signal_analysis_tab_changed|_on_mtf_curve_tab_changed" dicom_viewer.py
rg -n "build_window_b_analysis_panel|Notebook\(" window_b_manager.py window_b_panel_factory.py
```
