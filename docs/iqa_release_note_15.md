# 모두바 15회차 IQA Release Note

## 1) 한 줄 요약
15회차에서는 IQA를 단순 SSIM/PSNR/MSE/HIST 출력에서 확장해, **Reference/Target + ROI/옵션 + Context/Warnings + History/Session + Save Report(TXT/JSON/CSV/All)**까지 추적 가능한 영상 품질 비교 모듈로 정리했습니다.

## 2) 사용자 관점 변경 사항
- Reference / Target 선택
- Full Image / ROI 비교
- Input Mode 선택
  - Raw DICOM Pixel
  - Modality LUT
  - Windowed Display
- Data Range 추적
- Photometric Invert 옵션
- IQA 결과 섹션화
  - Summary
  - Metrics
  - Histogram
  - Context
  - Warnings
- Save Report
  - TXT
  - JSON
  - CSV
  - All

## 3) 개발자 관점 변경 사항
- `iqa_metrics.py`
- `iqa_result_schema.py`
- `iqa_dicom_adapter.py`
- `iqa_export.py`
- `iqa_display.py`
- `iqa_ui_state.py`
- `iqa_histogram.py`
- `iqa_history.py`
- `iqa_report.py`
- `iqa_report_export.py`
- `iqa_report_file_export.py`
- `iqa_report_export_ui.py`
- `iqa_report_ui_export.py` (shim)
- `docs/` 문서 세트 추가

## 4) 핵심 정책
- 계산 로직 / 표시 로직 / export / UI 분리
- data_range 명시 및 context 보존
- scope=roi에서 ROI 없으면 full_image fallback 금지
- invalid 상태에서 stale metric 금지
- warning은 messagebox가 아니라 결과 영역에 표시
- report/file writer는 UI와 분리
- DICOM IQA는 **진단 정확도 판정이 아니라 영상 품질 비교 지표**

## 5) 테스트 baseline
- 현재 baseline: **178 passed, 0 warnings**
- 주요 범주:
  - IQA core metrics
  - DICOM adapter
  - display
  - ROI
  - histogram
  - history
  - session
  - report
  - file export
  - report UI export
  - documentation

## 6) Known limitations
- PDF/DOCX report 미지원
- Histogram 실제 graph overlay UI 미구현
- ROI polygon/mask 고급 처리 범위 제한 가능
- IQA는 진단 정확도 평가가 아님
- 임상 영상 해석은 사용자 전문 판단 필요

## 7) 다음 회차 후보
- 16회차: Signal Analysis 검증 복귀
  - SNR/CNR MATLAB reference 비교
  - Uniformity reference 비교
  - MTF reference 비교
  - Line Profile reference 비교
- IQA 후속 후보
  - Histogram graph overlay
  - PDF report
  - compact panel 최종 spacing polish
  - ROI 고급 mask/polygon 지원
