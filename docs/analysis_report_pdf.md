# Analysis Report PDF Export Foundation (21회차-A)

- PDF export foundation은 GUI 비의존 helper로 report model을 배포용 포맷(PDF)으로 저장하기 위해 도입했습니다.
- 데이터 흐름은 normalized model → report model → PDF export 입니다.

## Helpers
- `build_analysis_report_pdf_lines(report_model)`
- `render_analysis_report_pdf_bytes(report_model)`
- `export_analysis_report_to_pdf(report_model, path=None)`

## PDF 포함 내용
- report title, generated_at, metadata
- summary(analysis_count/valid_count/invalid_count/warning_count/analysis_types)
- SNR/CNR/Uniformity/MTF section
- status/validity, scalar metrics, warnings, reason_codes, roi_info, source_payload_keys
- MTF curve summary(point_count 중심)

## 정책
- invalid/reject result도 PDF section에서 제외하지 않습니다.
- warnings/reason_codes/roi_info/source_payload_keys를 표시합니다.
- MTF raw curve point 전체와 graph 렌더링은 이번 단계에서 포함하지 않습니다.
- Markdown/text report를 대체하지 않고 병행 포맷으로 유지합니다.

## 범위 경계
- viewer PDF export 버튼은 후속 단계입니다.
- report preview window는 후속 단계입니다.
- pass/fail threshold는 후속 단계입니다.
- 계산 로직은 변경하지 않았습니다.

## 21-B viewer PDF report export integration
- 21-B에서 viewer PDF report export 연결이 추가되었습니다.
- viewer PDF export는 normalized analysis result model 기반으로 report_model을 만든 뒤 PDF helper를 호출합니다.
- viewer는 `analysis_report_pdf.py`의 `export_analysis_report_to_pdf(...)`를 재사용합니다.
- `path=None`이면 filedialog로 저장 경로를 받고, 취소 시 파일을 쓰지 않고 `None`을 반환합니다.
- PDF는 사람이 읽는 배포용 report 포맷입니다.
- Markdown report와 PDF report는 모두 report_model을 소비합니다.
- JSON/CSV는 raw data 보존용이고 PDF/Markdown은 요약 report용입니다.
- PDF preview window는 후속 단계입니다.
- pass/fail threshold는 후속 단계입니다.
- 계산 로직은 변경하지 않았습니다.
- PDF export는 파일 저장용이고, 22-A preview는 Markdown/text 기반 확인용입니다.
- PDF 렌더링 preview는 아직 후속 단계입니다.
- PDF report는 optional threshold evaluation section을 출력할 수 있습니다.
- threshold chart/graph는 아직 구현하지 않습니다.
- PDF export도 selected threshold config를 명시적으로 요청한 경우에만 threshold section을 포함합니다.
