# Analysis Threshold Editor UX Foundation (27회차-B)

- viewer에서 current_threshold_config를 직접 편집할 수 있는 full threshold editor UX foundation을 추가했습니다.
- rule 편집 로직은 기존 helper(`analysis_threshold_editor.py`)를 재사용하고, UX는 별도 Toplevel window로 제공합니다.

## Display model schema
- `threshold_editor_display_schema_version: 1`
- `name`, `description`, `rule_count`, `selected_rule_id`, `rules[]`
- rule row: `rule_id`, `analysis_type`, `metric`, `operator`, `threshold`, `severity`, `label`, `is_selected`

## 표시/편집 정책
- rule list + rule detail text를 분리 표시합니다.
- Add/Update/Remove/Duplicate/Reorder는 viewer의 기존 rule-level editor methods를 호출합니다.
- validation은 기존 schema/operator/severity/finite threshold 정책을 따릅니다.
- current_threshold_config 편집 후 display cache를 갱신합니다.
- current_threshold_catalog는 자동 변경하지 않습니다.
- report/history 자동 threshold 삽입은 하지 않습니다.

## 범위 경계
- default clinical threshold를 제공하지 않습니다.
- built-in clinical preset을 제공하지 않습니다.
- catalog manager는 config 선택/관리 UX이고, editor UX는 단일 config rule 편집 UX입니다.
- threshold evaluation 계산 로직은 변경하지 않았습니다.

- editor에서 current_threshold_config를 편집해도 catalog는 자동 변경되지 않습니다.
- 27-C에서 명시 sync action으로 selected entry 저장/새 entry 저장이 가능합니다.
