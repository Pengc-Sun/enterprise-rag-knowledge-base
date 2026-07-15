import importlib.util
from pathlib import Path
from types import ModuleType


def load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "validate_workspace_migration.py"
    spec = importlib.util.spec_from_file_location("validate_workspace_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seeded_v1_ids_are_stable_and_unique() -> None:
    script = load_script()

    seeded_ids = script.seeded_v1_ids()

    assert set(seeded_ids) == {
        "user_id",
        "knowledge_base_id",
        "document_id",
        "chunk_id",
        "conversation_id",
        "message_id",
    }
    assert len(set(seeded_ids.values())) == len(seeded_ids)
    assert script.SEED_EMAIL == "workspace-migration-seed@example.com"


def test_default_workspace_slug_matches_day9_migration_pattern() -> None:
    script = load_script()

    slug = script.default_workspace_slug_for_seed_user()

    assert slug.startswith("v1-default-")
    assert "-" not in slug.removeprefix("v1-default-")
    assert slug.endswith(str(script.SEED_USER_ID).replace("-", ""))


def test_validation_requires_explicit_yes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    script = load_script()
    monkeypatch.setattr("sys.argv", ["validate_workspace_migration.py"])

    assert script.main() == 2
