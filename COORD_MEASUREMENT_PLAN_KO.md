# 좌표 고정 반복 측정 기능 추가를 위한 안전한 설계 분석 (구현 전)

본 문서는 현재 코드베이스(`dicom_viewer.py`, `dicom_loader.py`, `image_pipeline.py`)를 유지한 상태에서,
연구용 좌표 기반 반복 측정 기능을 **기존 동작을 깨지 않고** 확장하는 방법을 정리한 것이다.

## 목표 기능(구현 전 분석 범위)
1. 현재 마우스 픽셀 좌표 표시
2. 이미지 위 격자(Grid) 오버레이 토글
3. 사각형 ROI + 선(Line)을 픽셀 좌표로 저장
4. 같은 geometry 이미지에 저장 ROI/Line 재적용

---

## 1) 현재 아키텍처에서 어디에 두어야 하는가

현재 구조는 아래처럼 책임이 나뉘어 있다.
- `dicom_loader.py`: 파일 읽기/디코드/전송구문/캐시
- `image_pipeline.py`: 픽셀 정규화/표시 변환
- `dicom_viewer.py`: UI, 캔버스 이벤트, 오버레이 그리기, 보기 모드 상태

좌표/ROI/라인/격자는 **“표시 좌표계 + 사용자 인터랙션 + 오버레이 렌더링”** 문제이므로,
1차적으로는 `dicom_viewer.py`의 UI/오버레이 레이어에 붙는 것이 자연스럽다.

다만 안전한 확장을 위해, 계산/저장/검증 로직은 별도 모듈로 분리하는 것이 좋다.

---

## 2) 적절한 신규 모듈 제안

### A. `measurement_model.py` (순수 데이터/검증)
- 역할: ROI/Line 데이터 구조(dataclass), 직렬화(dict/json), geometry 호환성 검사
- 예시 구조
  - `ImageGeometry(rows, cols, pixel_spacing, orientation_signature...)`
  - `RectRoi(x0, y0, x1, y1)`  # 픽셀 인덱스
  - `LineMeasure(x0, y0, x1, y1)`
  - `MeasurementRecord(id, geometry, roi_list, line_list, source_path, created_at)`
- 이유: UI 코드에서 데이터 무결성 검증을 분리하면 회귀 위험이 낮아짐

### B. `measurement_mapper.py` (좌표 변환)
- 역할: 캔버스 좌표 ↔ 원본 픽셀 좌표 변환
- 핵심
  - 현재 zoom/pan/center 정렬을 반영한 역변환
  - 표시용 `PhotoImage` 크기와 원본 frame shape의 비율 보정
  - 경계 클램프(0..cols-1, 0..rows-1)
- 이유: 가장 오류가 나기 쉬운 부분을 한 곳에 모아 테스트 가능하게 함

### C. `measurement_store.py` (저장/불러오기)
- 역할: JSON 파일 저장/로드, 버전 필드 관리, geometry 매칭/불일치 사유 반환
- 저장 위치: 프로젝트 루트 또는 사용자 지정 경로(초기엔 루트 고정이 안전)
- 이유: 추후 DB/CSV 전환이 쉬워지고 viewer 수정 범위 최소화

### D. (선택) `overlay_measurement_renderer.py` (그리기 유틸)
- 역할: 캔버스에 ROI/Line/Grid/좌표 텍스트를 그리는 공용 함수
- 이유: single/compare/multi 확장 시 중복 감소

---

## 3) 가장 안전한 구현 순서

### Step 0. 읽기 전용 기반 먼저
- 마우스 이동 시 “현재 픽셀 좌표” 표시만 추가
- 저장/편집 없이, 기존 pan/zoom/WL 동작에 영향 없는 경로로 구현
- 완료 기준: 좌표 라벨이 정확히 갱신되고 기존 단축키/드래그 동작 무변화

### Step 1. Grid 오버레이 토글
- 오버레이 계층(`overlay` 태그)만 사용해 그리기
- 이미지 데이터 변경 금지, 렌더 후 캔버스에 선만 추가
- 완료 기준: grid on/off가 프레임 전환·줌·패닝 후에도 안정적으로 유지

### Step 2. ROI/Line “그리기-미저장”
- 임시 객체만 생성/표시(메모리 내 상태)
- 저장 기능 없이 좌표 계산/렌더링만 검증
- 완료 기준: 드래그로 사각형/선 표시, 좌표가 픽셀 단위로 일관

### Step 3. 저장/로드 추가
- `measurement_store.py`로 JSON 저장/로드
- 최소 스키마(버전, geometry, shapes)부터 시작
- 완료 기준: 같은 이미지 재로드 시 동일 위치에 복원

### Step 4. “같은 geometry” 재적용
- geometry 매칭 성공 시만 적용
- 불일치 시 사용자에게 이유 명확히 안내(해상도/spacing 차이 등)
- 완료 기준: 다른 파일이라도 geometry 동일하면 ROI/Line 위치가 재현

### Step 5. compare/multiview 확장(선택)
- 단일 뷰 안정화 후 비교 뷰에 확장
- 멀티뷰 편집은 마지막 단계로 미룸(복잡도 큼)

---

## 4) 현재 동작을 깨지 않기 위해 피해야 할 것

1. **기존 마우스 바인딩을 바로 교체하지 말 것**
   - 현재 좌클릭 pan, 우클릭 WL drag 흐름에 직접 개입하면 회귀 위험이 큼
   - 측정 모드를 별도 토글로 분리하고, 비측정 모드에서는 기존 핸들러 100% 유지

2. **원본 프레임 배열을 수정하지 말 것**
   - 반전/그리드/ROI 라인은 모두 캔버스 오버레이 또는 표시 단계에서만 적용

3. **좌표계를 섞지 말 것**
   - canvas/display/pixel 좌표를 명시적으로 분리
   - 변환 함수는 단일 모듈(`measurement_mapper.py`)에서만 수행

4. **geometry 매칭 기준을 느슨하게 두지 말 것**
   - 최소 기준: Rows/Columns
   - 권장 기준: PixelSpacing(가능 시), Orientation 관련 태그
   - 기준 불충분 시 “재적용 금지 + 안내”가 안전

5. **초기부터 compare/multiview 편집까지 한 번에 넣지 말 것**
   - 단계적 확장 원칙을 지키지 않으면 이벤트 충돌 가능성 증가

6. **저장 포맷을 초기에 과복잡하게 설계하지 말 것**
   - 버전 필드 + 최소 필드부터 시작하고 점진 확장

---

## 5) 권장 최소 UI 추가(안전 버전)

- 상단 체크박스/버튼
  - `좌표 표시`
  - `Grid`
  - `측정 모드(ROI/Line)`
  - `측정 저장`, `측정 불러오기`, `재적용`
- 상태 라벨
  - `Cursor: x, y` (픽셀)
  - `Geometry match: OK/FAIL`

UI 구조 자체는 유지하고, 기존 toolbar에 컨트롤만 추가하는 방식이 안전하다.

---

## 결론

가장 안전한 접근은
- **(1) 좌표 표시 → (2) grid → (3) 임시 ROI/Line → (4) 저장/로드 → (5) geometry 재적용** 순으로,
- 계산/저장 책임을 `measurement_*` 모듈로 분리하고,
- `dicom_viewer.py`에는 최소한의 이벤트 연결/렌더 호출만 남기는 것이다.

이렇게 하면 현재 앱 동작(파일 열기, 프레임 이동, 비교/멀티뷰, WL/줌/팬)을 보존하면서 연구용 반복 측정 기능을 안정적으로 확장할 수 있다.
