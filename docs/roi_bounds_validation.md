# ROI Bounds Validation Foundation (31-A)
- 목적: ROI preset 좌표가 manifest의 Rows/Columns image bounds 내인지 실행 전에 검증.
- 입력: DICOM batch manifest + ROI preset + 분석 대상.
- 출력: ROI bounds validation result(별도 layer).
- 본 단계는 DICOM pixel data를 읽지 않으며 dcmread를 호출하지 않습니다.
- 본 단계는 SNR/CNR/Uniformity/MTF batch calculation을 실행하지 않습니다.
- ROI resolver 변경 없음.
- physical unit/pixel spacing validation 및 MTF edge orientation validation은 후속 단계.
- DICOM batch execution은 후속 단계.

- 31-B2에서 ROI bounds validation 결과는 execution plan viewer 입력으로 재사용되며 schema 변경은 없습니다.
- 31-B에서는 bounds validation 결과가 execution task readiness 판단(실행 가능/차단 사유)에 반영됩니다.
