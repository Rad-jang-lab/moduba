# Analysis Result Model Integration (18회차-A)

Reference validation 단계(SNR/CNR, Uniformity, MTF)는 closure 가능한 상태이며, 이제 제품 레이어(UI/export/report) 공통 소비를 위해 result model을 도입합니다.

## Common schema

```json
{
  "analysis_type": "snr|cnr|uniformity|mtf",
  "status": "...",
  "validity": "...",
  "metrics": {"name": 0.0},
  "curves": {"curve_name": {"x": [], "y": []}},
  "warnings": [],
  "reason_codes": [],
  "roi_info": {},
  "source_payload_keys": []
}
```

## Mapping
- SNR: `result` -> `metrics.snr`
- CNR: `result` -> `metrics.cnr`
- Uniformity: `result.value` -> `metrics.uniformity`
- MTF scalar: `key_mtf_metrics` finite numeric entries -> `metrics.*`
- MTF curve: `mtf_curve.frequency_cy_per_pixel`/`mtf_curve.mtf` -> `curves.mtf.x`/`curves.mtf.y`

## Invalid policy
- payload가 invalid/reject여도 `status`, `validity`, `warnings`, `reason_codes`를 보존합니다.
- non-finite scalar metric은 metrics에 넣지 않고 reason/warning으로 플래그 처리합니다.

## Scope boundary
- 이번 회차는 model helper + tests까지만 포함합니다.
- UI/export/report 구현은 시작하지 않았습니다.
- 계산 로직(SNR/CNR/Uniformity/MTF)은 변경하지 않았습니다.

## 18-B viewer display integration
- Raw `analysis_last_run` payload는 그대로 유지하고, viewer는 추가로 normalized/display 캐시를 보유합니다.
  - `analysis_last_run_normalized`: `normalize_analysis_result` 출력
  - `analysis_last_run_display`: viewer 표시용 구조(`build_analysis_display_model`) 출력
- Display model schema:
  - `analysis_type`, `title`, `status_text`, `validity_text`
  - `metric_rows` (`name/value/raw_value`)
  - `curve_summaries` (`name/point_count/x_label/y_label`)
  - `warning_lines`, `reason_lines`, `roi_lines`
- 표시 정책:
  - SNR/CNR/Uniformity/MTF 모두 동일한 display schema를 사용
  - invalid 결과도 warnings/reason_codes를 표시
  - MTF는 이번 단계에서 curve graph를 추가하지 않고 point count summary만 표시
- Export/report 구현은 여전히 시작하지 않았고, 다음 단계에서 common model 기반으로 진행합니다.

## 19-A export foundation linkage
- viewer display model과 export snapshot은 모두 동일한 normalized analysis result model을 소비합니다.
- 19-A에서 JSON/CSV export foundation(`analysis_result_export.py`)이 추가되었습니다.
- export 상세 정책/row schema는 `docs/analysis_result_export.md`에서 다룹니다.
- viewer export UI 및 PDF/report는 후속 단계(다음 회차) 범위입니다.
- normalized model은 viewer display뿐 아니라 viewer JSON/CSV export에서도 사용됩니다.
- export 상세 정책은 `docs/analysis_result_export.md`를 따릅니다.
- 20-A에서 normalized model 기반 report data model(`analysis_report_model.py`)이 추가되었습니다.
- viewer display, JSON/CSV export, report model이 모두 normalized analysis result model을 소비합니다.
- report 상세 정책은 `docs/analysis_report_model.md`에서 다룹니다.
- normalized model은 viewer display, JSON/CSV export, report model, viewer Markdown report export에서 공통으로 사용됩니다.
- normalized model은 viewer display, JSON/CSV export, Markdown report, PDF report foundation의 공통 입력으로 사용됩니다.
- normalized model은 viewer display, JSON/CSV export, Markdown report export, PDF report export의 공통 입력으로 사용됩니다.
- normalized model은 viewer display, JSON/CSV export, Markdown/PDF report export, report preview의 공통 입력으로 사용됩니다.
- normalized model은 viewer display, JSON/CSV export, Markdown/PDF report export, report preview, QC history foundation의 공통 입력으로 사용됩니다.
- normalized model은 history record의 기반이고, history viewer는 history record/export_snapshot을 소비합니다.
- normalized model은 viewer display, JSON/CSV export, Markdown/PDF report export, report preview, QC history, threshold evaluation의 공통 입력으로 사용됩니다.
- normalized model은 threshold evaluation의 입력이며, threshold evaluation은 report/history에 optional로 연결될 수 있습니다.
- normalized model은 selected threshold config 평가의 입력으로도 사용됩니다.
- normalized model은 selected threshold config evaluation의 입력으로 사용되며, report/history에는 선택적으로 연결됩니다.

- normalized model은 editor helper로 만든 threshold config 평가에도 동일하게 입력으로 사용됩니다.

- normalized model은 catalog에서 적용된 threshold config 평가에도 동일하게 사용됩니다.

- normalized model은 editor UX로 수정된 threshold config 평가에도 동일하게 사용됩니다.

- normalized model은 sync된 threshold config 평가에도 동일하게 사용됩니다.

- normalized result는 history record를 거쳐 summary/trend 분석의 기반이 됩니다.

- 30-A DICOM batch manifest는 아직 normalized result를 생성하지 않으며, 후속 batch analysis execution 이후 normalized result/history record로 이어질 수 있습니다.

- ROI preset은 normalized result를 생성하지 않으며 후속 analysis execution의 입력 정의로 사용됩니다.

- DICOM batch plan은 normalized result를 생성하지 않으며 execution 이후에만 연결됩니다.

- ROI bounds validation은 normalized result를 생성하지 않는 execution 전 validation 산출물입니다.
- execution plan 역시 아직 normalized result를 생성하지 않으며, actual execution 이후 normalized result/history record로 연결될 예정입니다.

- 이번 단계에서는 raw execution result를 normalized result로 자동 변환하지 않으며, 후속 adapter에서 raw_result_payload normalization을 연결할 예정입니다.


## Batch Execution Normalization Reuse
- normalized execution result는 task 단위로 `normalize_analysis_result`를 재사용합니다.
- 아직 history/report/batch QC 자동 연결은 수행하지 않습니다.
