"""Write docs/advice-for-clinical-review.md from the code. Run from backend/:

python -m scripts.export_advice
"""

import os
import sys

sys.path.append(os.getcwd())

from pathlib import Path

from app.core.clinical_review import render_review_sheet

TARGET = Path(__file__).resolve().parent.parent.parent / "docs" / "advice-for-clinical-review.md"


def main():
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(render_review_sheet(), encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
