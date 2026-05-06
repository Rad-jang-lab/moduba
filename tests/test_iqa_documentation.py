from pathlib import Path


def test_iqa_docs_exist_and_keywords():
    paths = [
        Path("docs/iqa_architecture.md"),
        Path("docs/iqa_user_workflow.md"),
        Path("docs/iqa_testing_matrix.md"),
        Path("docs/iqa_release_note_15.md"),
        Path("docs/iqa_handoff_checklist.md"),
    ]
    for p in paths:
        assert p.exists()
    content = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    for kw in [
        "IQAResult",
        "iqa_dicom_adapter",
        "ROI",
        "Histogram",
        "Report",
        "Save Report",
        "no auto-recompute",
        "178 passed",
        "0 warnings",
        "진단 정확도 판정이 아니라 영상 품질 비교 지표",
        "pytest",
        "Session",
        "Signal Analysis",
    ]:
        assert kw in content
