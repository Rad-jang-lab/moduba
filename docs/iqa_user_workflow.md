# IQA User Workflow

## 1) 기본 실행 절차
1. Reference 지정
2. Target 지정
3. Input Mode 선택 (Raw DICOM Pixel / Modality LUT / Windowed Display)
4. Scope 선택 (Full Image / ROI)
5. ROI 선택(ROI scope일 때)
6. Run IQA
7. 결과(요약/지표/히스토그램/컨텍스트/경고) 확인
8. Report 저장(TXT/JSON/CSV/All) - Export Format 선택 후 **Save Report** 클릭

## 2) Full Image vs ROI
- Full Image: 배경 포함 가능, 전역 품질 비교.
- ROI: 관심영역 품질 비교.
- ROI 없음 + scope=roi: 실행 불가(`missing_scope_roi`).
- Full Image에서 background warning은 해석 주의 신호.

## 3) Input Mode
- Raw DICOM Pixel: 원 픽셀 값 기반.
- Modality LUT: LUT 적용 후 비교.
- Windowed Display: 표시용 윈도우 기반(일반적으로 8-bit/255 기준 맥락).

## 4) Data Range
- Auto
- Bits Stored
- Actual Union
- 표시 모드/컨텍스트에 따라 실제 사용값(`data_range_used`) 확인.

## 5) 결과 해석
- MSE/RMSE: 오차 크기.
- PSNR: 높을수록 유사.
- SSIM: 구조 유사도(1에 가까울수록 유사).
- HIST corr: 밝기 분포 유사도.
- histogram distribution hint: target이 밝아짐/어두워짐 등 분포 방향 힌트.

## 6) Warning 해석
- `missing_scope_roi`: ROI 선택 필요.
- `roi_bbox_clipped_to_image_bounds`: ROI 경계 보정됨.
- `invalid_roi_bbox_after_clip`: 유효 비교 영역 없음.
- `missing_bits_stored`: bits 정보 없어 대체 정책 사용.
- `monochrome1_without_inversion`: MONOCHROME1 반전 미적용.
- `full_image_background`: 배경 포함 가능.
- `same_image`: 동일 영상 비교(검증용 가능).

## 7) Report 저장
- TXT: 사람이 읽기 쉬운 보고서.
- JSON: 구조화 payload.
- CSV: flat row 중심.
- All: txt/json/csv 동시 저장.
- 상태 문구: 저장 완료 / 저장 취소 / 저장할 report 없음 / 저장 실패.
- 계산 실행은 **Run IQA**, 저장은 **Save Report**로 구분.

## 8) 주의 문구
IQA 결과는 **영상 품질 비교 지표**입니다. 진단 정확도/의학적 판단을 직접 의미하지 않습니다.
