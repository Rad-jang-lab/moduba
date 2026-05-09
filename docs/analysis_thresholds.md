# Analysis Threshold Evaluation Foundation (24회차-A)

- threshold evaluation layer는 normalized analysis result model 기반으로 설정형 pass/fail/warn 판정을 수행하기 위해 도입했습니다.
- 하드코딩 임상 기준 없이 threshold config 입력을 받아 평가합니다.

## Threshold config schema
- `threshold_schema_version: 1`
- `name`, `description`, `rules[]`
- rule: `rule_id`, `analysis_type`, `metric`, `operator`, `threshold`, `severity`, `label`

## Supported operators
- `>`, `>=`, `<`, `<=`, `==`, `!=`

## Severity 정책
- `fail`, `warn`

## Evaluation result schema
- `threshold_evaluation_schema_version`, `generated_at`, `config_name`, `overall_status`, `summary`, `results[]`

## overall_status 정책
- fail rule 실패 존재: `fail`
- fail 없음 + warn rule 실패 존재: `warn`
- 모든 rule pass: `pass`
- 평가 가능한 rule 없음: `not_evaluated`

## missing/invalid/non-finite 처리
- analysis missing / metric missing / invalid analysis / non-finite metric은 `not_evaluated` + reason 기록

## 범위 경계
- pass/fail 기준 하드코딩 없음
- threshold UI/config editor 후속 단계
- report/history 자동 삽입 없음
- trend chart/batch QC 후속 단계
- 계산 로직 변경 없음

## 24-B optional integration
- 24-B에서 threshold evaluation을 report/history에 optional로 통합했습니다.
- threshold_config가 명시적으로 제공된 경우에만 evaluation이 생성됩니다.
- default clinical threshold는 여전히 하드코딩하지 않습니다.
- threshold UI/config editor는 후속 단계이며, report/history 자동 기본 판정은 없습니다.
- 25-A에서 threshold config load/save/display foundation이 추가되었습니다.
- threshold evaluation은 여전히 명시 config 기반이며 default clinical threshold를 하드코딩하지 않습니다.
- config editor/preset catalog는 후속 단계입니다.
- threshold evaluation은 selected config 또는 명시 config를 통해 report/history에 optional로 포함할 수 있습니다.
- default threshold는 여전히 제공하지 않습니다.

- threshold evaluation engine은 editor helper로 생성/수정된 config도 동일하게 `validate_threshold_config` 후 evaluate합니다.
- evaluation logic 자체는 변경하지 않았습니다.

- threshold evaluation은 catalog에서 선택해 viewer에 적용한 threshold config도 동일하게 validate/evaluate합니다.
- evaluation logic 자체는 변경하지 않았습니다.

- catalog manager에서 적용된 current_threshold_config도 동일 threshold evaluation engine으로 평가됩니다.
- batch QC threshold evaluation도 동일 `validate_threshold_config` + `evaluate_analysis_thresholds` engine을 사용합니다.
- selected-threshold batch wrapper는 config 선택 UX layer일 뿐, threshold evaluation logic/스키마를 변경하지 않습니다.
- evaluation logic은 변경하지 않았습니다.

- editor UX로 수정된 config도 동일 threshold evaluation engine으로 평가됩니다.
- evaluation logic은 변경하지 않았습니다.

- sync된 config도 동일 threshold evaluation engine으로 평가됩니다.
- evaluation logic은 변경하지 않았습니다.

- threshold_evaluation overall_status는 history summary에서 pass/warn/fail/not_evaluated/missing 집계에 사용될 수 있습니다.
