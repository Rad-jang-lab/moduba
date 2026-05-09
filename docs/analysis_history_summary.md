# Analysis History Summary & Trend Foundation (28회차-A)
- history JSONL records에서 파생 요약/추세 model을 생성하는 foundation입니다.
- trend chart/batch QC는 포함하지 않습니다.
- summary는 export_snapshot.results와 optional threshold_evaluation을 집계합니다.
- scalar metric만 trend 대상으로 사용하며 MTF curve raw data는 text dump하지 않습니다.
- history summary/trend는 history records 집계 layer이고, batch QC는 여러 history record를 batch item/run으로 묶어 별도 산출물을 만드는 layer입니다.
- selected-threshold batch UX는 batch item별 threshold evaluation을 명시적으로 적용하는 viewer convenience layer입니다.
- non-finite/missing metric은 point 제외 후 카운트로 기록합니다.
- viewer는 Toplevel+Text 기반 summary viewer만 제공합니다.
- 계산/threshold evaluation 로직은 변경하지 않았습니다.
