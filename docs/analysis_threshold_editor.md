# Analysis Threshold Editor Foundation (26회차-A)

- threshold config editor foundation은 사용자 제공 threshold config를 안전하게 rule 단위로 편집하기 위한 GUI 비의존 helper 계층입니다.
- threshold config schema 자체는 유지하고, 편집 결과도 동일 schema로 validate됩니다.

## 왜 도입했는가
- load/save/display만으로는 rule 단위 수정(add/update/remove/reorder/duplicate)이 번거롭기 때문에, deterministic하고 재사용 가능한 편집 helper가 필요합니다.

## Helper 목록
- `validate_threshold_rule(rule)`
- `add_threshold_rule(config, rule)`
- `update_threshold_rule(config, rule_id, updates)`
- `remove_threshold_rule(config, rule_id)`
- `reorder_threshold_rules(config, rule_ids)`
- `duplicate_threshold_rule(config, source_rule_id, new_rule_id)`
- `get_threshold_rule(config, rule_id)`
- `list_threshold_rules(config)`

## 정책
- mutation 방지: 입력 config/rule을 직접 수정하지 않고 새 config를 반환합니다.
- validation 재사용: `validate_threshold_config(...)`를 통해 schema/operator/severity/finite threshold 정책을 재검증합니다.
- rule-level 제약:
  - duplicate `rule_id` 금지
  - 없는 `rule_id` update/remove/duplicate 금지
  - reorder는 기존 rule_id 집합과 정확히 일치해야 함
- optional field(`description` 등)는 보존합니다.
- default clinical threshold는 제공/추가하지 않습니다.

## 범위 경계
- threshold preset catalog는 후속 단계입니다.
- full GUI editor window는 후속 단계입니다.
- report/history 자동 threshold 삽입 정책은 변경하지 않았습니다.
- threshold evaluation 계산 로직은 변경하지 않았습니다.

- editor helper는 단일 threshold config의 rule-level 편집을 담당합니다.
- catalog helper는 여러 threshold config의 저장/선택/입출력을 담당합니다.
- full catalog manager UI는 여전히 후속 단계입니다.

- rule-level editor helper는 여전히 helper 중심이며 full GUI editor는 후속 단계입니다.
- catalog manager는 rule 편집 UI가 아니라 threshold config 선택/관리 UI입니다.

- 27-B에서 full threshold editor UX foundation이 추가되었습니다.
- 기존 editor helper가 viewer editor window에서 재사용됩니다.
- rule-level helper는 UX에서 호출되는 엔진이며 default clinical threshold를 제공하지 않습니다.
