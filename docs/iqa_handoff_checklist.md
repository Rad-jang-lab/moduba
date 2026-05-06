# IQA Handoff Checklist (15회차)

## 1) 15회차 완료 체크리스트
- [ ] pytest 178 passed 확인
- [ ] warnings 0 확인
- [ ] IQA report export UI 작동 확인
- [ ] Save Report TXT/JSON/CSV/All 확인
- [ ] ROI scope fallback 금지 확인
- [ ] session restore no auto-recompute 확인
- [ ] docs/iqa_architecture.md 존재
- [ ] docs/iqa_user_workflow.md 존재
- [ ] docs/iqa_testing_matrix.md 존재

## 2) 수동 QA 체크리스트
- [ ] DICOM 2개 로드
- [ ] Set Ref / Set Target
- [ ] Run IQA
- [ ] Full Image 결과 확인
- [ ] ROI 선택 후 Selected ROI 실행
- [ ] ROI 없는 상태에서 Selected ROI 실행 불가 확인
- [ ] Windowed Display 선택 시 결과 context 확인
- [ ] Save Report TXT
- [ ] Save Report JSON
- [ ] Save Report CSV
- [ ] Save Report All
- [ ] Session 저장 후 복원
- [ ] 이전 IQA 결과가 자동 재계산이 아니라 복원 요약으로 표시되는지 확인

## 3) 개발자 QA 체크리스트
- [ ] 신규 IQA 모듈 py_compile
- [ ] pytest -q
- [ ] warnings 0
- [ ] no messagebox
- [ ] no PDF/DOCX
- [ ] iqa_report_file_export.py에 tkinter/filedialog import 없음
- [ ] iqa_report_export_ui.py에 tkinter/filedialog/messagebox import 없음
- [ ] dicom_viewer.py가 계산 로직을 직접 과도하게 들고 있지 않은지 확인

## 4) 16회차 진입 전 확인
- [ ] baseline commit/PR 기록
- [ ] 변경 파일 목록 확인
- [ ] 테스트 결과 기록
- [ ] 다음 회차 작업 범위 확정
- [ ] Signal Analysis / MATLAB reference 우선순위 확정
