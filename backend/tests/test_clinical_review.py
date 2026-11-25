from pathlib import Path

from app.core import factor_insights as fi
from app.core.clinical_review import (
    DEFAULT_REVIEW_STATUS,
    LABELS_LONG,
    extract_review_status,
    generated_review_sections,
    render_review_sheet,
)

SHEET = Path(__file__).resolve().parent.parent.parent / "docs" / "advice-for-clinical-review.md"


def test_every_habit_is_on_the_review_sheet():
    assert set(LABELS_LONG) == set(fi.RISK_PREDICATES) == set(fi.RISK_TEXT)
    sheet = render_review_sheet()
    for name in fi.RISK_PREDICATES:
        assert fi.TIPS[name] in sheet


def test_the_committed_review_sheet_matches_the_code():
    """Detect generated-section divergence; clinical sign-off remains a human step."""
    committed = SHEET.read_text(encoding="utf-8")
    assert generated_review_sections(committed) == generated_review_sections(render_review_sheet())


def test_the_committed_review_status_is_intentionally_unsigned():
    committed = SHEET.read_text(encoding="utf-8")
    assert extract_review_status(committed) == DEFAULT_REVIEW_STATUS
    assert "intentionally blank" in DEFAULT_REVIEW_STATUS


def test_human_review_entries_are_preserved_outside_the_generated_sections():
    reviewed = render_review_sheet("Reviewed by the clinical team on 25 November 2026.")
    assert extract_review_status(reviewed) == "Reviewed by the clinical team on 25 November 2026."
    assert "Reviewed by the clinical team" not in generated_review_sections(reviewed)
