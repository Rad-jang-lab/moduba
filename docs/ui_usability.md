# UI Usability Updates (UX-1)

## Scope
- ROI 생성 직후 선택 상태를 즉시 반영합니다.
- 메인 윈도우와 Window B에 명시적 resize grip을 추가해 크기 조절 클릭 편의성을 개선합니다.

## ROI Immediate Selection Policy
- **Free ROI**: 드래그 생성 완료 시 즉시 해당 ROI를 selected로 설정합니다.
- **Grid ROI**: 기존과 동일하게 생성/재선택 직후 selected를 유지합니다.
- **Line measurement**: 이번 정책의 자동 ROI 선택 대상이 아닙니다.

## Selection/Analysis UI Sync
- ROI 생성 즉시 선택 ID가 반영되어 selector/action button 상태가 즉시 갱신됩니다.

## Resize Grip
- `ttk.Sizegrip` 기반으로 bottom-right에 배치했습니다.
- 사용성 향상을 위해 약 24px hit area를 갖는 컨테이너에 배치했습니다.

## Non-goals (unchanged)
- SNR/CNR/Uniformity/MTF 계산 로직 및 공식
- ROI resolver
- Batch execution/history/report/threshold schema
- DomainStore 구조/세션 복원 구조
- 대규모 UI 레이아웃

## A/B Resize Scope
- 코드 기준 A/B는 별도 Toplevel이 아니라 main viewer 내부 `compare_container` 좌/우 panel입니다.
- 이번 UX-1에서는 대규모 compare layout 변경(PanedWindow 전환 등) 없이 유지합니다.
- 필요 시 UX-2에서 compare panel 전용 리사이즈 상호작용 개선을 후속으로 진행합니다.

## Safety
- resize grip은 `<Configure>` 시점에 `lift()` 재호출로 가려짐을 방지합니다.
- 창 종료/파괴 타이밍의 `TclError`는 helper 내부에서 안전하게 무시합니다.
