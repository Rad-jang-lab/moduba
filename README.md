# DICOM Viewer

`pydicom`과 `tkinter`를 사용해서 DICOM 파일을 열고 이미지를 표시하는 간단한 뷰어입니다.

## 기능

- 파일 선택기로 DICOM 파일 열기
- 폴더 선택기로 폴더 내부 DICOM 파일을 이름순으로 불러오기
- DICOM 이미지 표시
- 환자명, 모달리티, 해상도, 프레임 수 표시
- 이전/다음 버튼으로 이미지 넘기기
- 현재 몇 번째 이미지인지 표시
- 멀티프레임 DICOM에서 이전/다음 프레임 이동
- 비DICOM 파일과 Pixel Data가 없는 DICOM 파일은 폴더 스캔에서 자동 제외
- 압축된 DICOM은 설치된 픽셀 디코더가 없으면 원인을 안내하는 오류 메시지 표시
- 폴더 진단으로 정상 DICOM, 비DICOM, Pixel Data 없음, 압축 DICOM(Pixel Data 있음), 멀티프레임 DICOM을 개수와 파일명으로 요약
- 진단 결과 창에서 스크롤 가능한 상세 목록 확인 및 텍스트 파일 저장 가능

## 설치

Windows Python 기준:

```bash
py -m pip install -r requirements.txt
```

`tkinter`는 일반적인 Windows Python 설치에 기본 포함됩니다.

압축된 DICOM(JPEG, JPEG 2000 등)까지 보려면 필요에 따라 아래 패키지도 추가 설치합니다.

```bash
py -m pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg gdcm
```

## 실행

```bash
py dicom_viewer.py
```
