# Analysis Threshold Catalog Foundation (26회차-B)

- threshold catalog foundation은 여러 threshold config를 저장/선택/가져오기/내보내기 하기 위한 사용자 관리 저장소입니다.
- built-in clinical preset은 제공하지 않으며 default clinical threshold도 제공하지 않습니다.

## Catalog와 Config 관계
- threshold config: 단일 평가 규칙 세트.
- threshold catalog: 여러 threshold config를 `config_id` key로 보관하는 컨테이너.

## Catalog schema
- `threshold_catalog_schema_version: 1`
- `name`, `description`
- `selected_config_id` (선택 상태)
- `configs: {config_id: threshold_config}`

## 정책
- `config_id`는 stable string이며 catalog 내 unique해야 합니다.
- `selected_config_id`는 catalog 내부 선택 상태일 뿐 default clinical threshold가 아닙니다.
- load/save는 UTF-8 JSON, save는 `ensure_ascii=False`, `indent=2`, `sort_keys=True`로 deterministic 저장합니다.
- import/export는 threshold config JSON 단위로 동작합니다.
- validation은 nested threshold config까지 `validate_threshold_config`를 재사용합니다.

## Display model
- `threshold_catalog_display_schema_version: 1`
- `config_count`, `selected_config_id`, `entries[]`
- entries는 `config_id` 기준 정렬되고, `rule_count`와 `is_selected`를 포함합니다.

## Viewer 정책
- viewer는 `current_threshold_catalog`를 별도로 보관합니다.
- catalog selected config는 `apply_selected_catalog_threshold_config_to_viewer()`로 `current_threshold_config`에 명시 적용합니다.
- catalog selected 상태가 있어도 report/history 자동 threshold 삽입 정책은 변경하지 않았습니다.

## 범위 경계
- full catalog manager UI는 후속 단계입니다.
- full threshold GUI editor window는 후속 단계입니다.
- threshold evaluation 계산 로직은 변경하지 않았습니다.

- 27-A에서 viewer threshold catalog manager UX foundation이 추가되었습니다.
- catalog manager는 config 목록 확인/선택/적용/import/export/remove를 위한 최소 Toplevel UI입니다.
- selected_config_id는 catalog 내부 선택 상태이며, Apply Selected to Viewer를 호출해야 current_threshold_config에 반영됩니다.
- current_threshold_config가 있어도 report/history 자동 threshold 삽입은 하지 않습니다.
- built-in clinical preset은 제공하지 않으며 계산 로직은 변경하지 않았습니다.
- full rule editor UI는 여전히 후속 단계입니다.

- catalog manager는 config 선택/관리 UI이고, threshold editor UX는 current_threshold_config의 rule 편집 UI입니다.
- editor에서 current_threshold_config를 바꿔도 current_threshold_catalog는 자동 변경되지 않습니다.
- catalog 반영은 후속 명시 save/update flow가 필요합니다.

- Apply Selected to Viewer는 catalog -> current config 방향 복사입니다.
- Save Current to Selected는 current config -> catalog selected entry 반영입니다.
- `selected_config_id`는 batch QC에 자동 적용되지 않습니다.
- batch QC에서 catalog 선택 config를 사용하려면 Apply Selected to Viewer로 `current_threshold_config`에 반영한 후, selected-threshold batch wrapper를 명시 호출해야 합니다.
- 두 동작은 반대 방향 sync이며 자동 동기화가 아닙니다.
