# Analysis History Trend Chart UX Foundation (28회차-B)
- trend series data model을 viewer chart model로 변환하는 최소 UX foundation입니다.
- chart model은 scalar metric trend만 다루며 MTF curve raw graph를 그리지 않습니다.
- threshold_overall_status는 metadata로만 보존하며 threshold logic을 재계산하지 않습니다.
- empty/one-point trend를 안전하게 처리합니다.
- Canvas + text 기반 최소 viewer를 제공하며 dashboard/batch QC는 후속 단계입니다.
- 계산 로직은 변경하지 않았습니다.
