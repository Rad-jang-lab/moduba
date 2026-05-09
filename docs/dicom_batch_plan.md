
# DICOM Batch Plan Foundation (30회차-C)
- manifest + roi preset을 결합해 analysis readiness plan을 생성합니다.
- pixel data read/actual batch calculation/ROI resolver 변경은 하지 않습니다.


- batch plan은 role completeness readiness, ROI bounds validation은 Rows/Columns 기반 별도 validation layer입니다.
- 31-A에서는 plan에 bounds result를 자동 삽입하지 않습니다.

- 31-B2에서 batch plan 결과는 execution plan viewer 입력으로 재사용되며 schema 변경은 없습니다.
- batch plan은 role completeness readiness layer이고, execution plan은 batch plan + ROI bounds validation 결합으로 executable/blocked task list를 생성합니다.
