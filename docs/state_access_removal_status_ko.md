# 1부. lifecycle 일원화 및 store 단일 소유권 정리 문서

## 변경 영향 범위 요약
- session/apply 경로를 `store.load_session(snapshot)` 중심으로 재구성했다.
- snapshot이 없는 구세션은 적용 시점에 snapshot으로 마이그레이션한 뒤 동일 경로로 로드한다.
- 기존 기능/버튼/메뉴/사용자 흐름은 유지했다.

## 파일별 변경 요약
- `dicom_viewer.py`
  - `_migrate_legacy_session_to_store_snapshot()` 추가: 구세션 payload를 store snapshot으로 변환.
  - `apply_session()`를 단일 로드 경로(`store.load_session(snapshot)`) 중심으로 전환.
  - group/session/hisotry 재구성은 store selector 결과 기반으로 수행.
- `docs/state_access_removal_status_ko.md`
  - 남은 LEGACY_BRIDGE와 제거 조건, 완료 기준 충족 여부를 갱신.

## 제거된 direct access 목록
- session apply에서 legacy direct rebuild 분기를 제거하고, snapshot 기반 단일 로드 경로로 통일.
- group/session direct field ownership은 제거된 상태를 유지(store map selector).
- analysis/history read selector-only 상태 유지.

## 남은 LEGACY_BRIDGE / legacy adapter 목록
- `LEGACY_BRIDGE:` measurement adapter
  - `_legacy_bridge_set_persistent_measurements`
  - `_legacy_bridge_append_measurement`
  - `_legacy_bridge_extend_measurements`
  - `_legacy_bridge_pop_last_measurement`
  - `_legacy_bridge_remove_measurement_by_id`
- `LEGACY_BRIDGE:` analysis/history cache 보조 write 경로
- 남아 있는 이유: draw/runtime object가 현재 Measurement runtime list를 기대
- 제거 조건: draw layer를 store selector 결과 기반 runtime projection으로 치환

## 구세션 fallback 구조 및 마이그레이션 전략
- 기존: snapshot 없음 -> legacy rebuild 분기
- 현재: snapshot 없음 -> `_migrate_legacy_session_to_store_snapshot()`으로 변환 -> `store.load_session(snapshot)`
- 즉, apply/load 실행 경로는 단일화되고, 구세션 처리는 사전 변환 단계로 격리됨

## session save/load/apply/reset 경로 정리 결과
- save: store_snapshot 포함
- load/apply: `store.load_session(snapshot)` 단일 경로
- reset: store 재생성 후 selector 기반 초기화
- 결과: lifecycle primary path 단일화 완료 (구세션은 변환 후 동일 경로)

## panel refresh 정리 결과
- 기존 targeted refresh 함수 재사용 유지.
- full redraw/update/update_idletasks/nested loop 도입 없음.

## store snapshot 기반 UI 재구성 가능 여부
- analysis/history/group/session은 snapshot 기반으로 재구성 가능.
- measurement draw object는 adapter 경유 재구성(완전 100%는 미완료).

## 구조 완료 판단 기준 충족 여부
- 기준 1(legacy rebuild 분기 제거): 충족
- 기준 2(measurement snapshot-only 재구성): 미충족
- 기준 3(draw object runtime 재생성): 부분 충족(재생성은 하나 adapter 경유)
- 기준 4(새 LEGACY_BRIDGE 추가 금지): 충족

## Phase 4 종료 조건
1. measurement LEGACY_BRIDGE adapter 제거
2. draw object 생성을 store selector projection으로 완전 치환
3. analysis/history cache 보조 write 경로 제거
4. snapshot-only 100% UI 복원 테스트 통과

---

### 필수 보고 지표
- `store.load_session(snapshot)` 단일 진입점 완성 여부: 완료(구세션은 변환 후 동일 경로)
- 구세션 fallback 제거 가능 여부/전략: 가능, 변환 함수로 대체 완료
- measurement adapter 제거 가능 여부: 가능하나 draw 계층 치환 필요
- store snapshot 100% UI 재구성 여부: measurement adapter 잔존으로 미완료
- 남은 `LEGACY_BRIDGE` 최종 목록/계획: measurement adapter + cache 보조, Phase 4 종료 조건에서 제거
- 구조 완료 판단 기준: 4개 중 3개 충족, measurement adapter 제거 잔여

