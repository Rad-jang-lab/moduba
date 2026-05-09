# Analysis History Store Foundation (23회차-A)

- QC history layer는 normalized 결과 기반 실행 기록을 누적 저장/복원하기 위해 도입했습니다.
- 관계: normalized model -> export snapshot + report summary -> history record.

## History helper
- `build_analysis_history_record(...)`
- `append_analysis_history_record(...)`
- `load_analysis_history_records(...)`
- `filter_analysis_history_records(...)`
- `export_analysis_history_to_json(...)`

## History record schema
- `history_schema_version`, `record_id`, `generated_at`, `metadata`, `summary`, `export_snapshot`
- `summary`는 report model summary를 재사용합니다.
- `export_snapshot`은 export helper를 재사용해 raw normalized 보존성을 유지합니다.

## JSONL 저장 정책
- 한 줄당 한 record JSON object(UTF-8)
- append 모드로 누적 저장, 파일 없으면 생성
- 빈 파일 load는 `[]`
- malformed JSON line / schema version mismatch는 `ValueError`

## Filtering 정책
- `analysis_type`: summary.analysis_types 포함 여부 기준
- `validity`: export_snapshot.results 내부 validity 포함 여부 기준
- 입력 records는 mutate하지 않습니다.

## 보존 및 요약 정책
- invalid/reject 결과도 history에 포함
- warnings/reason_codes/roi_info/source_payload_keys는 export_snapshot에 보존
- MTF raw curve data는 export_snapshot에서 보존, history summary는 point_count 중심 요약(report summary) 역할

## 범위 경계
- 이번 단계에서는 history viewer UI, trend chart, batch QC, pass/fail threshold를 구현하지 않았습니다.
- 계산 로직은 변경하지 않았습니다.

## 23-B history viewer UX foundation
- 23-B에서 history viewer UX foundation이 추가되었습니다.
- JSONL history storage를 load한 뒤 history display model로 목록/상세 표시를 구성합니다.
- history display model schema는 `history_display_schema_version`, `record_count`, `filters`, `rows`를 사용합니다.
- record detail text는 record_id/generated_at/summary/analysis별 status-validity-metrics-warnings-reasons-roi를 포함합니다.
- filtering은 analysis_type/validity 기준이며, storage filter helper를 재사용합니다.
- invalid/reject result도 목록/상세에서 숨기지 않습니다.
- warnings/reason_codes/roi_info/source_payload_keys를 상세에서 표시합니다.
- MTF curve raw data는 직접 덤프하지 않고 summary(point_count) 중심으로 표시합니다.
- history viewer는 목록/상세 확인용이며 trend chart가 아닙니다.
- pass/fail threshold와 batch QC는 후속 단계입니다.
- 계산 로직은 변경하지 않았습니다.
- 24-A threshold evaluation은 별도 evaluation layer이며, history schema에는 아직 자동 삽입하지 않습니다.
- 후속 단계에서 history record에 threshold evaluation summary를 선택적으로 포함할 수 있습니다.
- history record는 optional `threshold_evaluation`을 보존할 수 있습니다.
- 기존 threshold_evaluation 없는 records도 유효하며, history display/detail은 threshold evaluation이 있으면 표시합니다.
- selected threshold config가 있어도 history record는 threshold_config가 명시 전달된 경우에만 threshold_evaluation을 포함합니다.
- 자동 history 판정 삽입은 후속 단계입니다.
- history record는 selected threshold config를 명시적으로 요청한 경우에만 threshold_evaluation을 포함합니다.
- 기본 history append는 threshold_evaluation 없이 backward-compatible하게 유지됩니다.

- editor로 current_threshold_config를 수정해도 history의 threshold_evaluation은 명시 요청 시에만 포함됩니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- catalog selected config가 있어도 history는 명시 요청 시에만 threshold_evaluation을 포함합니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- catalog manager에서 config를 적용해도 history는 명시 요청 시에만 threshold_evaluation을 포함합니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- editor로 current_threshold_config를 수정해도 history는 명시 요청 시에만 threshold_evaluation을 포함합니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- catalog sync는 history 자동 threshold 삽입 정책을 변경하지 않습니다.
- threshold_evaluation은 명시 요청 시에만 포함됩니다.

- 28-A에서 history records 기반 summary/trend foundation이 추가되었습니다.
- history JSONL은 누적 저장소이고 summary/trend는 이를 읽어 만든 파생 model입니다.
- history display는 개별 record 목록/상세이고 history summary는 여러 record의 집계/추세입니다.

- history JSONL은 분석 결과 저장소이고, DICOM batch manifest는 분석 전 입력 목록/metadata 준비 산출물입니다.

- ROI preset은 history record가 아니라 분석 전 입력 정의입니다.

- DICOM batch plan은 history record가 아니라 분석 전 실행 계획입니다.
