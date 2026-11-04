from pathlib import Path

from app.core import factor_insights as fi
from app.core.clinical_review import LABELS_LONG, render_review_sheet

SHEET = Path(__file__).resolve().parent.parent.parent / "docs" / "advice-for-clinical-review.md"


def test_every_habit_is_on_the_review_sheet():
    assert set(LABELS_LONG) == set(fi.RISK_PREDICATES) == set(fi.RISK_TEXT)
    sheet = render_review_sheet()
    for name in fi.RISK_PREDICATES:
        assert fi.TIPS[name] in sheet


def test_the_committed_review_sheet_matches_the_code():
    """If this fails, run `python -m scripts.export_advice` and have the changes re-reviewed."""
    assert SHEET.read_text(encoding="utf-8") == render_review_sheet()
