# Signal Analysis Reference Validation Foundation (16회차-A)

## Scope order
Validation rollout order is fixed as:
1. SNR/CNR
2. Uniformity
3. MTF
4. Line Profile

## Baseline
15회차 baseline before this change:
- `pytest`: 178 passed
- warnings: 0

IQA validation and Signal Analysis validation must remain independent.

## Reference formulas
- **SNR**: `mean(signal ROI) / std(noise ROI)`
- **CNR (standard_noise)**: `abs(mean(target ROI) - mean(reference ROI)) / std(noise ROI)`

Reference calculations in this phase use deterministic numeric arrays and independent helpers (not the viewer calculation function).

## ROI fixture policy
Test fixtures must construct ROIs in resolver-compatible flow with roles:
- signal ROI
- background ROI
- noise ROI
- CNR target/reference ROI

Priority chain remains unchanged:
- direct/manual ROI ID
- UI combobox selection
- DomainStore role auto-bind
- compatibility fallback
- structured invalid result

## Tolerance policy
Default numeric comparison policy:
- absolute tolerance (`atol`): `1e-6`
- relative tolerance (`rtol`): `1e-6`

If only display-rounded values are available in a future path, tolerance may need to be relaxed with rationale recorded in test/doc updates.

## MATLAB reference file expected format
This phase adds loader helpers only. Real MATLAB exports can be integrated later.

- JSON loader: dictionary payload (e.g., `{"metric":"SNR","value":1.23,...}`)
- CSV loader: table rows parsed by header columns (e.g., `metric,value,...`)

Recommended future fields:
- `metric` (`SNR` or `CNR`)
- `formula`
- `value`
- `atol`
- `rtol`
- ROI identity metadata (`signal_roi_id`, `noise_roi_id`, ...)

## Regression intent
- Keep resolver/DomainStore/session restoration architecture from 15회차 unchanged.
- Do not change SNR/CNR production formulas in this phase.
- Preserve IQA behavior and warning-free pytest execution.


## Uniformity reference formula
- **Uniformity (max_min)**: `100 * (1 - (max - min) / (max + min))`
- This follows current Moduba `max_min` policy and is used for deterministic reference validation in 17회차-A.

- Uniformity 값은 **100에 가까울수록 더 균일**한 상태를 의미합니다.
- `max + min == 0` (또는 `<= 0`)인 경우는 유효한 수치 결과로 처리하지 않으며, reference helper는 `ValueError`로 처리하고 viewer 경로는 invalid 결과로 분류한 뒤 normalize 단계에서 실패하도록 검증합니다.


## MTF Phase 1
- MTF는 curve/FFT/sampling/normalization 요소가 결합되어 있어 **Phase 1에서는 result schema 및 scalar metric normalization 검증**에 집중합니다.
- 이번 단계의 우선 검증 metric 예시는 `mtf50`입니다.
- curve-level MATLAB reference comparison은 **Phase 2**에서 수행 예정입니다.
- tolerance 정책은 동일하게 `atol=1e-6`, `rtol=1e-6`를 사용합니다.
- MATLAB reference 예상 포맷은 JSON(`metric,value,tolerance`) 또는 CSV(`metric,value,atol,rtol`)입니다.
- Actual viewer execution path (`_execute_mtf_pipeline`) returns payload keys such as `calculation_status`, `calculation_validity`, `key_mtf_metrics`, `mtf_curve`, `esf_curve`, `lsf_curve`, `warnings`, `reason_codes`.
- `normalize_mtf_result` currently supports scalar extraction from `key_mtf_metrics[metric_key]` with root-level `result[metric_key]` fallback.
- Phase 1 comparison scope: scalar metric sanity/normalization and invalid-structure handling only.
- Remaining Phase 2 scope: curve-level MATLAB reference comparison for frequency/value arrays and interpolation-sensitive diagnostics.

- Phase 2 curve normalization path: `result["mtf_curve"]["frequency_cy_per_pixel"]` and `result["mtf_curve"]["mtf"]`.
- Curve-level normalization validates non-empty, same-length, finite, ascending frequency arrays before comparison.
- Scalar normalization(`normalize_mtf_result`) targets single metric extraction (e.g., `mtf50`), while curve normalization(`normalize_mtf_curve`) validates and returns full frequency/value arrays.
- Current Phase 2 reference fixture compares actual execution-path curve against deterministic reference fixture generated from the same execution path; full external MATLAB curve fixture alignment remains as follow-up scope.
- No MTF/ESF/LSF/FFT calculation logic was changed in this phase.

- External fixture location: `tests/fixtures/mtf_external_reference_curve.json`.
- Fixture schema: `{source, generation_note, roi_condition, pixel_spacing_mm, frequency_cy_per_pixel, mtf}`.
- Comparison method: normalize actual payload with `normalize_mtf_curve`, normalize fixture arrays to same shape, and compare frequency/value pairs with `compare_mtf_curve_to_reference`.
- Frequency grid handling: if fixture and actual grids differ, validation layer interpolates fixture `mtf` onto actual `frequency` grid using linear interpolation (`numpy.interp`) before tolerance check.
- Tolerance: `atol=1e-6`, `rtol=1e-6` (no automatic relaxation).
- Error reporting: on mismatch, tests report max absolute error, max relative error, mismatch index/frequency, actual value, reference value.
- Current closure status: deterministic external fixture comparison is passing; full MATLAB-origin multi-condition fixture expansion remains follow-up work.


## Next step
- MTF external reference validation 이후 reference validation 단계는 closure 가능 상태입니다.
- 다음 단계는 analysis result model integration이며, 본 문서는 계산 검증 기록으로 유지합니다.
- 제품 기능 확장(UI/export/report)은 `docs/analysis_result_model.md`에서 다룹니다.
