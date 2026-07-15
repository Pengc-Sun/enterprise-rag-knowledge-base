import os
import subprocess

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_WORKSPACE_MIGRATION_TESTS") != "1",
    reason="Set RUN_WORKSPACE_MIGRATION_TESTS=1 to run database-mutating migration validation.",
)
def test_seeded_v1_data_migrates_to_workspace() -> None:
    result = subprocess.run(
        [".venv/bin/python", "scripts/validate_workspace_migration.py", "--yes", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"all_workspace_ids_match": true' in result.stdout
    assert '"message_count": 1' in result.stdout
