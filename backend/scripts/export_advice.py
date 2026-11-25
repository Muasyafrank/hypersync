"""Write docs/advice-for-clinical-review.md from the code. Run from backend/:

python -m scripts.export_advice
"""

import os
import sys

sys.path.append(os.getcwd())

from pathlib import Path

from app.core.clinical_review import extract_review_status, render_review_sheet

TARGET = Path(__file__).resolve().parent.parent.parent / "docs" / "advice-for-clinical-review.md"


def main():
    TARGET.parent.mkdir(exist_ok=True)
    existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    review_status = extract_review_status(existing)
    TARGET.write_text(render_review_sheet(review_status), encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
