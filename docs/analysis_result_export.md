# Analysis Result Export Foundation Closure (19회차-A)

## Why the export layer was introduced
- 분석 결과를 UI/내부 payload 형태에 직접 의존하지 않고, **공통 normalized model 기반으로 JSON/CSV로 안정적으로 내보내기** 위해 export layer를 분리했습니다.
- 목적은 viewer export UI/PDF/report 구현 이전에, export core를 deterministic 하게 고정(closing)하는 것입니다.

## Relationship: normalized model ↔ export snapshot
- export는 raw payload를 직접 다루지 않고, `normalized_results`(analysis_type별 normalized dict)를 입력으로 받습니다.
- `build_analysis_export_snapshot(...)`는 normalized model을 export용 snapshot으로 감싸서:
  - schema version,
  - timezone-aware `generated_at`,
  - optional `metadata`,
  - deterministic ordered `results`
  를 포함한 단일 구조를 만듭니다.

## `build_analysis_export_snapshot` schema

```json
{
  "export_schema_version": 1,
  "generated_at": "ISO-8601 timezone-aware timestamp",
  "metadata": {},
  "results": {
    "snr": {"... normalized result ...": "..."},
    "cnr": {"...": "..."},
    "uniformity": {"...": "..."},
    "mtf": {"...": "..."}
  }
}
```

### Validation policy
- `normalized_results is None`이면 `ValueError`.
- analysis_type payload가 `None`이면 `ValueError`.
- payload 내부의 숫자(int/float)에 non-finite(`NaN`, `Inf`)가 있으면 `ValueError`.

## JSON export policy
- `export_analysis_results_to_json(...)`는 snapshot을 `indent=2`, `ensure_ascii=False`로 직렬화합니다.
- `path=None`이면 문자열만 반환합니다.
- `path`가 있으면 UTF-8 파일로 저장한 뒤 동일 문자열을 반환합니다.

## CSV export policy
- `export_analysis_results_to_csv(...)`는 snapshot의 각 analysis_type 결과를 row 기반으로 평탄화합니다.
- `path=None`이면 CSV 문자열 반환, `path`가 있으면 파일 저장 후 동일 문자열 반환.
- CSV writer는 `lineterminator="\n"`을 사용해 in-memory 문자열과 파일 read 결과의 newline 동작을 deterministic하게 유지합니다.

### CSV row schema
공통 컬럼:
- `export_schema_version`
- `generated_at`
- `analysis_type`
- `status`
- `validity`
- `item_type`
- `item_name`
- `item_index`
- `value`
- `x`
- `y`
- `point_count`
- `warnings_json`
- `reason_codes_json`
- `roi_info_json`
- `source_payload_keys_json`

### `result_summary` row
- analysis_type당 1행 생성.
- `item_type="result_summary"`, `item_name="summary"`.
- 결과의 상태/유효성 및 warnings/reason/roi/source keys를 함께 보존합니다.

### `metric` row
- `metrics` 딕셔너리 key별 1행 생성.
- `item_type="metric"`, `item_name=<metric name>`, `value=<metric value>`.

### `curve_point` row
- `curves`의 각 curve에서 `(x, y)` pair별 1행 생성.
- `item_type="curve_point"`, `item_name=<curve name>`, `item_index=<point index>`, `x`, `y`, `point_count` 포함.

## SNR/CNR/Uniformity/MTF export behavior
- 네 analysis type 모두 동일한 snapshot/row policy를 사용합니다.
- SNR/CNR/Uniformity scalar는 metric row로 export됩니다.
- MTF scalar metrics(`mtf50` 등)는 metric row로 export됩니다.

## MTF curve export behavior
- normalized `curves.mtf.x`/`curves.mtf.y`를 curve_point rows로 export합니다.
- point index와 point_count를 함께 내보내 curve row 검증이 가능하도록 유지합니다.

## Invalid/reject result export behavior
- 결과가 invalid/reject여도 export를 차단하지 않습니다(단, non-finite numeric은 예외).
- `status`, `validity`, `warnings`, `reason_codes`는 summary row 및 공통 컬럼 JSON 필드에 보존됩니다.

## Preservation policy
다음 필드는 export 과정에서 손실 없이 보존됩니다.
- `warnings` → `warnings_json`
- `reason_codes` → `reason_codes_json`
- `roi_info` → `roi_info_json`
- `source_payload_keys` → `source_payload_keys_json`

## Timestamp policy
- 기본 `generated_at`은 `datetime.now(timezone.utc).isoformat()`으로 생성합니다.
- 따라서 timezone-aware timestamp 정책(UTC offset 포함)을 유지합니다.

## Deterministic ordering policy
- analysis type 순서는 우선순위 `snr → cnr → uniformity → mtf`, 나머지는 알파벳 정렬입니다.
- metric/curve 이름은 정렬하여 row 생성 순서를 고정합니다.

## Scope boundary for 19회차-A closure
- 이번 회차는 export foundation closure 문서화/회귀 확인 단계입니다.
- **viewer export UI 버튼 구현은 아직 시작하지 않았습니다.**
- **PDF/report 구현은 아직 시작하지 않았습니다.**
- **계산 로직(SNR/CNR/Uniformity/MTF)은 변경하지 않았습니다.**
- **reference validation 범위를 새로 확장하지 않았습니다.**

## 19-B viewer JSON/CSV export UI integration
- viewer의 분석 결과 export 경로는 `analysis_last_run_normalized`를 우선 사용합니다.
- normalized cache가 비어 있고 raw `analysis_last_run`가 있으면 `normalize_analysis_last_run(...)`로 normalized cache를 생성해 export에 사용합니다.
- JSON/CSV export는 새 serialization을 만들지 않고 `analysis_result_export.py` helper(`export_analysis_results_to_json`, `export_analysis_results_to_csv`)를 그대로 사용합니다.
- 파일 저장 경로 선택에서 dialog를 취소하면 파일을 쓰지 않고 조용히 반환합니다.
- PDF/report 구현은 이 단계에서도 시작하지 않았습니다.
- 계산 로직(SNR/CNR/Uniformity/MTF)은 변경하지 않았습니다.
- JSON/CSV export는 raw data 보존용이며, report model은 사람이 읽는 요약용 역할을 가집니다.
- MTF curve raw point export는 JSON/CSV에서 담당하고, report는 curve summary만 포함합니다.
- JSON/CSV는 raw 보존용이고 Markdown report는 사람이 읽는 요약용입니다.
- 둘 다 normalized model을 출발점으로 사용하지만 목적이 다릅니다.
- history record는 export snapshot을 포함해 raw normalized result 보존성을 유지합니다.
- JSON/CSV export는 단일 export 산출물이고, history JSONL은 누적 기록 저장소입니다.
- history viewer는 history JSONL record 내부의 export_snapshot을 읽어 목록/상세 표시를 구성합니다.
