# Analysis Report Data Model (20회차-A)

## 도입 이유
- JSON/CSV export 이후 단계에서 사람이 읽을 수 있는 QC report 기반이 필요합니다.
- viewer preview, PDF export, history 재사용을 위해 **normalized analysis result model 기반 공통 report model**을 먼저 고정합니다.

## normalized model과 report model 관계
- 입력은 `normalize_analysis_last_run(...)` 결과 또는 viewer `analysis_last_run_normalized`입니다.
- raw `analysis_last_run` payload를 직접 report 입력으로 사용하지 않습니다.

## Report model schema

```json
{
  "report_schema_version": 1,
  "generated_at": "ISO-8601 timezone-aware timestamp",
  "metadata": {},
  "summary": {
    "analysis_count": 0,
    "valid_count": 0,
    "invalid_count": 0,
    "warning_count": 0,
    "analysis_types": []
  },
  "sections": [
    {
      "analysis_type": "snr|cnr|uniformity|mtf",
      "title": "...",
      "status": "...",
      "validity": "...",
      "metrics": [{"name": "...", "value": 0.0, "formatted_value": "..."}],
      "curve_summaries": [{"name": "mtf", "point_count": 0, "x_label": "x", "y_label": "y"}],
      "warnings": [],
      "reason_codes": [],
      "roi_info": {},
      "source_payload_keys": []
    }
  ]
}
```

## Summary section 정책
- `analysis_count`: section 개수
- `valid_count` / `invalid_count`: `validity` 기준 집계
- `warning_count`: 모든 section warnings 길이 합
- `analysis_types`: deterministic 순서(snr, cnr, uniformity, mtf 우선)

## Analysis section 정책
- invalid/reject 결과도 숨기지 않고 section에 포함합니다.
- warnings/reason_codes/roi_info/source_payload_keys를 보존합니다.
- non-finite numeric 값 또는 `None` payload는 `ValueError`로 reject합니다.

## SNR/CNR/Uniformity/MTF 매핑
- SNR: `metrics.snr`를 report metrics에 포함
- CNR: `metrics.cnr`를 report metrics에 포함
- Uniformity: `metrics.uniformity`를 report metrics에 포함
- MTF scalar: `metrics.*`를 report metrics에 포함

## MTF curve summary 정책
- `curves["mtf"]`는 `curve_summaries`에 `point_count` 중심으로만 표시합니다.
- x/y raw 배열 전체는 report section에 직접 덤프하지 않습니다.
- curve raw data 보존/추출은 JSON/CSV export 레이어 책임입니다.

## Markdown/text report 역할
- `render_analysis_report_markdown(...)`은 report model을 사람이 읽는 Markdown 문자열로 렌더링합니다.
- 제목, 생성시각, metadata, summary, 분석별 section(상태/유효성/metrics/curve summary/warnings/reason)을 포함합니다.
- deterministic 순서로 출력해 preview/버전비교/회귀테스트가 가능합니다.

## 범위 경계
- 이번 단계는 **PDF 생성 구현이 아닙니다**.
- 이번 단계는 **viewer report UI 구현이 아닙니다**.
- pass/fail threshold 판정은 후속 단계입니다.
- 계산 로직(SNR/CNR/Uniformity/MTF)은 변경하지 않았습니다.

## 20-B viewer Markdown/text report export integration
- viewer는 `analysis_last_run_normalized`를 기준으로 Markdown/text report를 생성합니다.
- normalized cache가 비어 있고 raw `analysis_last_run`가 있으면 `normalize_analysis_last_run(...)`으로 cache를 생성해 사용합니다.
- viewer는 `build_analysis_report_model(...)`과 `render_analysis_report_markdown(...)` helper를 재사용합니다.
- report 저장은 `.md` 기본 확장자를 사용하며 UTF-8로 저장합니다.
- 파일 dialog 취소 시 파일을 쓰지 않고 `None`을 반환합니다.
- Markdown/text report는 사람이 읽는 요약용이며, raw JSON/CSV export를 대체하지 않습니다.
- MTF curve는 point_count summary만 포함합니다.
- PDF export와 viewer report preview window는 후속 단계입니다.
- 계산 로직은 변경하지 않았습니다.
- 21-A에서 report model 기반 PDF export foundation(`analysis_report_pdf.py`)이 추가되었습니다.
- Markdown/text report와 PDF report는 모두 report model을 소비합니다.
- PDF 상세 정책은 `docs/analysis_report_pdf.md`에서 다룹니다.
- viewer PDF export UI는 후속 단계입니다.
- report_model은 Markdown report뿐 아니라 viewer PDF export에서도 사용됩니다.
- PDF 상세는 `docs/analysis_report_pdf.md`에서 다룹니다.
- 22-A에서 viewer report preview UX가 추가되었습니다.
- preview는 report_model과 Markdown renderer를 재사용합니다.
- preview는 저장 전 사람이 읽는 report 내용을 확인하는 용도입니다.
- preview는 Markdown/text 기반이며 PDF preview가 아닙니다.
- MTF curve는 point_count summary만 표시하며 invalid/reject도 숨기지 않습니다.
- JSON/CSV export는 raw 보존, Markdown/PDF export는 저장 포맷, preview는 사전 확인 UX로 역할이 구분됩니다.
- 계산 로직은 변경하지 않았습니다.
- PDF preview, pass/fail threshold, history는 후속 단계입니다.
- history record는 report summary를 포함해 기록 목록/추세 분석의 기반으로 사용할 수 있습니다.
- 전체 사람이 읽는 report는 Markdown/PDF export가 담당하고, history summary는 목록/검색용 요약입니다.
- history summary는 report summary를 재사용하고, history viewer는 사람이 읽는 상세 텍스트를 제공하지만 full report export를 대체하지 않습니다.
- threshold evaluation은 아직 report model에 자동 포함하지 않습니다.
- 후속 단계에서 report에 QC 판정 섹션을 추가할 수 있습니다.
- report model은 optional `threshold_evaluation` section을 포함할 수 있습니다.
- Markdown/PDF report는 threshold_evaluation이 있을 때만 QC Threshold Evaluation section을 표시합니다.
- viewer에 selected threshold config가 있어도 report는 threshold_config가 명시 전달된 경우에만 threshold section을 포함합니다.
- 자동 삽입 정책은 후속 UX 단계입니다.
- report preview/export는 selected threshold config를 명시적으로 요청한 경우에만 QC Threshold Evaluation section을 포함합니다.
- 기본 report는 threshold section 없이 backward-compatible하게 유지됩니다.

- editor로 current_threshold_config를 수정해도 report의 threshold_evaluation은 명시 요청 시에만 포함됩니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- catalog selected config가 있어도 report는 명시 요청 시에만 threshold_evaluation을 포함합니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- catalog manager에서 config를 적용해도 report는 명시 요청 시에만 threshold_evaluation을 포함합니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- editor로 current_threshold_config를 수정해도 report는 명시 요청 시에만 threshold_evaluation을 포함합니다.
- 자동 삽입 정책은 변경하지 않았습니다.

- catalog sync는 report 자동 threshold 삽입 정책을 변경하지 않습니다.
- threshold_evaluation은 명시 요청 시에만 포함됩니다.

- report는 단일 실행 요약이고 history summary는 여러 실행 기록의 집계입니다.

- report는 분석 결과 기반 산출물이고, DICOM batch manifest는 분석 전 준비 산출물이므로 직접 동일한 레이어가 아닙니다.
