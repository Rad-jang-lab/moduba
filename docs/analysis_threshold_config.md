# Analysis Threshold Config Management (25회차-A)

- threshold config management layer는 사용자가 제공한 JSON config를 load/save/표시/적용하기 위한 foundation입니다.
- empty template는 rules=[]만 제공하며 기본 임상 기준값은 제공하지 않습니다.

## Helpers
- `build_empty_threshold_config(...)`
- `load_threshold_config(path)`
- `save_threshold_config(config, path)`
- `build_threshold_config_display_model(config)`
- `render_threshold_config_text(config)`

## 정책
- `validate_threshold_config` 재사용
- load/save는 UTF-8 JSON, save는 ensure_ascii=False, indent=2, deterministic 정렬
- viewer는 selected threshold config를 instance 속성으로 보관
- selected config로 현재 분석 결과를 evaluate하고 text preview 제공

## 범위 경계
- threshold config editor 후속 단계
- threshold preset catalog 후속 단계
- report/history 자동 삽입 후속 단계
- 계산 로직 변경 없음
- 25-B에서 selected threshold config를 report preview/export/history 저장에 명시적으로 사용할 수 있게 되었습니다.
- current_threshold_config가 있어도 자동 삽입하지 않으며 `use_selected_threshold_config=True` 또는 selected-threshold 전용 method로만 포함됩니다.
- 명시 threshold_config와 selected config가 동시에 있으면 명시 threshold_config를 우선합니다.
- threshold config editor/preset catalog는 여전히 후속 단계입니다.

- 26-A에서 threshold config editor foundation(`analysis_threshold_editor.py`)이 추가되었습니다.
- load/save/display helper에 더해 rule-level add/update/remove/reorder/duplicate/get/list helper가 추가되었습니다.
- default clinical threshold는 여전히 제공하지 않습니다.
- preset catalog와 full GUI editor window는 여전히 후속 단계입니다.

- 26-B에서 여러 threshold config를 관리하는 catalog foundation(`analysis_threshold_catalog.py`)이 추가되었습니다.
- 단일 config load/save는 개별 threshold config JSON을 다루고, catalog load/save는 다중 config+selected 상태를 함께 다룹니다.
- catalog selected config는 명시적으로 current_threshold_config에 적용할 수 있습니다.
- built-in clinical preset은 여전히 제공하지 않습니다.

- 단일 config load/save는 개별 JSON 관리이고, catalog manager UX는 다중 config 선택/적용/입출력을 담당합니다.
- catalog manager에서 선택한 config는 Apply Selected to Viewer를 통해 current_threshold_config로 적용할 수 있습니다.

- single config load/save/display/edit UX가 추가되었습니다.
- threshold config schema 자체는 변경하지 않았습니다.

- current_threshold_config는 catalog 적용 또는 editor 수정으로 변경될 수 있고, catalog 반영은 명시 sync action으로 수행됩니다.
- current_threshold_config는 batch QC에서도 자동 적용되지 않으며, `use_selected_threshold_config=True`(또는 selected-threshold wrapper)로 명시 요청된 경우에만 사용됩니다.
- batch QC에 대한 자동 threshold 적용 정책은 없습니다.
