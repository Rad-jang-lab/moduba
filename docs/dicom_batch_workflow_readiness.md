# DICOM Batch Workflow Readiness

- 목적: batch 실행 전 readiness를 한눈에 요약.
- 입력: execution plan, ROI role validation report, pixel capability text, execution/history/QC/report 상태.
- 상태: `ready` / `warning` / `blocked`.
- strict ROI validation: 기본 False, True + invalid ROI report면 pixel run block.
- Window B UI: Refresh Workflow Readiness, Require valid ROI roles before pixel run.
- 비목표: 계산식/ROI resolver/DICOM read/schema 변경/대규모 UI 개편/messagebox 추가.
