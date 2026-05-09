# Batch QC Report Export

## 목적
Batch QC run을 사용자 검토/저장 가능한 산출물로 변환합니다.

## 데이터 흐름
current_batch_qc_run -> batch_qc_report_model -> text preview -> raw JSON export -> raw CSV export -> report text export -> report PDF export

## raw export vs report export
- raw JSON/CSV: batch_qc_run 원본 schema 기반
- report text/PDF: 사람이 읽기 쉬운 report model 기반

## threshold 표시 정책
- threshold_evaluation이 있으면 overall_status 표시
- 없으면 missing

## 비목표
- Batch QC schema 변경 없음
- 계산 공식 변경 없음
- ROI resolver 변경 없음
- DICOM pixel data read 없음
- Window B 대규모 재설계 없음
