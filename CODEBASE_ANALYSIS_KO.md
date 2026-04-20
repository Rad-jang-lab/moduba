# Moduba DICOM Viewer 코드베이스 분석 (dicom_viewer.py 중심)

## 1) 현재 프로그램 동작 방식

`dicom_viewer.py`는 하나의 대형 클래스(`DicomViewer`) 안에서 상태 관리, UI 구성/이벤트, DICOM 로딩/디코딩, 픽셀 정규화, 오버레이 렌더링, 폴더 진단을 모두 수행한다.

핵심 실행 흐름은 다음과 같다.

1. `main()`에서 `tk.Tk()`를 생성하고 `DicomViewer(root)`를 초기화한다.
2. 생성자(`__init__`)에서 상태 변수/캐시를 준비하고 UI를 구성한다.
3. 사용자 입력(파일 열기/폴더 열기/진단/단축키/마우스) 이벤트가 모두 `DicomViewer` 메서드로 들어온다.
4. 파일 선택 시 `_load_file()` 경유로 `_get_decoded_file()` → `_read_dataset_for_display()` → `_extract_frames()` 순으로 데이터셋과 프레임을 만든다.
5. 프레임 표시 시 `_show_frame()`가 `_frame_to_photoimage()`를 통해 정규화/리사이즈한 이미지를 Canvas에 그린다.
6. 오버레이(기본 정보, 촬영 정보)는 `_draw_single_view_overlays()` 또는 비교 모드의 `_draw_compare_overlays()`에서 텍스트로 합성된다.

또한 단일/멀티/비교 보기 모드 전환, 썸네일 큐 처리, 폴더 진단 리포트 생성이 모두 동일 클래스에 결합되어 있다.

## 2) UI 로직으로 볼 수 있는 부분

아래 범위는 주로 tkinter 위젯 생성, 배치, 이벤트 바인딩, 상태 라벨 갱신 등 UI concern이다.

- 상단 툴바, 캔버스/스크롤바, 멀티뷰/비교뷰 컨테이너 생성: `_build_ui()`
- 키보드 단축키 바인딩: `_bind_shortcuts()`
- 비교 패널 위젯 생성: `_create_compare_panel()`
- 멀티뷰 페이지/타일 렌더링 및 이벤트: `render_multiview_page()` 계열
- 오버레이 설정 팝업: `open_overlay_settings()` 계열
- 폴더 진단 결과 팝업 및 저장 버튼 UI: `_show_diagnosis_window()`

즉, tkinter `ttk.Button/Label/Canvas/Toplevel`를 직접 다루는 코드 대부분이 UI 레이어다.

## 3) DICOM 로딩/처리 로직으로 볼 수 있는 부분

아래 범위는 데이터 I/O/디코딩/검증/정규화가 중심이다.

- 파일 읽기와 오류 분류/캐시:
  - `_get_decoded_file()`
  - `_read_dataset_for_display()`
  - `_ensure_transfer_syntax_supported()`
  - `_is_probable_decode_error()`
- 프레임 추출/차원 처리:
  - `_extract_frames()`
- 폴더 스캔/진단:
  - `_collect_folder_candidates()`
  - `_get_quick_scan_exclusion_reason()`
  - `_diagnose_folder_contents()`
  - `_categorize_display_failure()`
- 표시 전 픽셀 처리:
  - `_normalize_frame_for_dataset()`
  - `_apply_window_level_to_array()`
  - `_apply_photometric_interpretation()`
  - `_scale_to_uint8()`
- 메타데이터 포맷팅/오버레이 값 수집:
  - `_get_metadata_dataset()`
  - `_get_first_available_value()` 및 포맷터들
  - `_collect_overlay_values()`

다만 현재는 이 처리 로직도 클래스 내부에 있어 UI 코드와 강하게 결합되어 있다.

## 4) 안전한 업그레이드를 위해 “가장 먼저” 분리해야 할 것

가장 먼저 분리할 대상은 **순수 DICOM 로딩/변환 파이프라인**이다.

우선순위를 이렇게 잡는 것이 안전하다.

1. **파일 로드/디코드 서비스 분리**
   - `_get_decoded_file`, `_read_dataset_for_display`, `_extract_frames`, transfer syntax 체크를 `DicomLoader`(예: `services/dicom_loader.py`)로 이동.
   - 이유: I/O + 예외 처리 + 캐시가 기능 핵심이며, UI 변경 없이 테스트하기 가장 쉽다.

2. **픽셀 정규화/윈도우레벨 계산 분리**
   - `_initialize_window_level`, `_apply_window_level_to_array`, `_scale_to_uint8`, `_normalize_frame_for_dataset`를 `ImagePipeline` 유틸/서비스로 이동.
   - 이유: Viewer 기능 확장(VOI LUT 옵션, 프리셋, modality별 처리) 시 안정성을 좌우한다.

3. **폴더 진단 로직 분리**
   - `_diagnose_folder_contents`와 관련 함수들을 `FolderDiagnosisService`로 이동.
   - 이유: UI와 독립적으로 회귀 테스트 가능하며, 대용량 폴더 최적화도 분리 후 쉽다.

오버레이/멀티뷰/비교모드는 UI-상태와 결합이 더 커서, 1~3을 먼저 안정화한 후 분리하는 편이 리스크가 낮다.

## 기능 보존을 최우선으로 한 단계별 리팩터링 계획

아래 단계는 **매 단계마다 동작 동일성 유지**가 목표다.

### 단계 0: 안전망 먼저
- `tests/`를 만들고 “현재 동작을 고정하는 스냅샷 테스트”부터 추가.
- 최소 범위:
  - `_extract_frames` 입력 shape별 결과
  - window/level 클리핑 결과
  - 폴더 진단 카테고리 분류
- UI 통합테스트는 최소화하고, 서비스 레벨 단위 테스트 위주로 시작.

### 단계 1: 데이터 구조 도입 (동작 변화 없음)
- `ViewerState`/`PanelState` 같은 `dataclass`만 도입하고 기존 dict 접근을 점진 치환.
- 메서드 시그니처와 외부 동작은 그대로 유지.
- 목적: 타입 안정성과 리팩터링 안전성 증가.

### 단계 2: DicomLoader 추출
- 새 파일 `services/dicom_loader.py` 생성.
- 아래 메서드만 1차 이동:
  - read/decoded cache
  - transfer syntax 지원 확인
  - frame extraction
- `DicomViewer`는 호출만 하도록 얇게 변경.
- 완료 기준: 화면 동작 동일 + 관련 테스트 통과.

### 단계 3: ImagePipeline 추출
- 새 파일 `services/image_pipeline.py` 생성.
- window/level 계산/적용, photometric 반전, 8bit 스케일링 이동.
- compare/single 모두 같은 파이프라인 함수를 사용하게 통합.
- 완료 기준: 동일 파일에서 렌더된 이미지 통계(예: min/max, shape)가 기존과 동일.

### 단계 4: FolderDiagnosisService 추출
- 새 파일 `services/folder_diagnosis.py` 생성.
- 폴더 스캔/분류/리포트 데이터 생성만 담당.
- tkinter messagebox/Toplevel 호출은 `DicomViewer`에 남기고, 서비스는 순수 데이터 반환.
- 완료 기준: 기존 진단 텍스트 결과와 동일(또는 의도된 차이를 명시).

### 단계 5: OverlayFormatter 분리
- 오버레이 value 수집/텍스트 포맷팅 로직을 `overlay/formatter.py`로 분리.
- Canvas draw 호출은 UI 레이어에 남기되, “무슨 텍스트를 그릴지”만 외부에서 전달.

### 단계 6: ViewController 정리
- 단일/멀티/비교 모드 전환을 `controller` 성격 클래스로 정리.
- 키보드/마우스 이벤트는 UI 바인딩 함수에서 controller 호출만 하도록 축소.

### 단계 7: 파일 구조 정리(최종)
- 예시 구조:
  - `ui/viewer.py` (tkinter)
  - `services/dicom_loader.py`
  - `services/image_pipeline.py`
  - `services/folder_diagnosis.py`
  - `overlay/formatter.py`
  - `models/state.py`
- 진입점(`dicom_viewer.py`)은 bootstrap 용도로 축소.

## 리팩터링 시 주의할 리스크

- 캐시 키/수명 변경 시 메모리 사용량 급증 가능.
- compare/single 경로의 중복 로직 제거 과정에서 미세 동작(줌 중심, W/L drag 민감도) 깨질 수 있음.
- 오버레이 줄바꿈/말줄임은 UI 폭 의존이라 회귀가 쉽게 발생.

따라서 각 단계에서 “기능 추가”는 금지하고, 먼저 분리/동일동작 유지에만 집중하는 전략이 가장 안전하다.
