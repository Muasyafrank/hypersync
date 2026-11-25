"""Migration safeguards that do not need a running database."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_offline_sql_generation_includes_the_daily_factor_constraint():
    """Offline deployments must not fail merely because duplicates cannot be inspected."""
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": "postgresql://offline:offline@localhost/hypersync_offline",
            "SECRET_KEY": "offline-migration-test-secret",
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "base:head", "--sql"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "uq_environmental_factors_patient_logged_date" in result.stdout
