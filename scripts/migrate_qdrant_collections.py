"""
Qdrant Collection Migration Utility — Agentic AI Evaluator

Migrates Qdrant collections to new names with 'ai-evaluator-demo-trials-' prefix.
Uses the same collections connected in this project: form/demo chunks and analysis reports.

When to use:
    - When migrating collections for production deployment
    - When renaming collections to avoid conflicts
    - One-time migration task

Usage:
    # From project root
    uv run python scripts/migrate_qdrant_collections.py

    # Or
    python -m scripts.migrate_qdrant_collections

Configuration:
    - Collection names are read from .env (Qdrant_Form, Qdrant_Analysis_Report)
    - New names use prefix: ai-evaluator-demo-trials-
    - Edit MIGRATE_ALL and COLLECTIONS_TO_MIGRATE below if needed
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path so "src" can be imported (run from any cwd)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load .env before importing config
from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from src.core.config import (
    QDRANT_LOCAL_URI,
    QDRANT_API_KEY,
    QDRANT_COLECTION_DEMO,
    QDRANT_COLLECTION_ANALYSIS,
)

# New collection names with prefix (used in this project)
PREFIX = "ai-evaluator-demo-trials-"

# Collection mappings: OLD_NAME (from .env) -> NEW_NAME
# Built in main() from current .env so you migrate whatever names you have now
def _build_collection_mappings():
    m = {}
    if QDRANT_COLECTION_DEMO:
        m[QDRANT_COLECTION_DEMO] = f"{PREFIX}form"
    if QDRANT_COLLECTION_ANALYSIS:
        m[QDRANT_COLLECTION_ANALYSIS] = f"{PREFIX}analysis"
    return m

# Migration settings
MIGRATE_ALL = True  # Set to False to migrate specific collections only
COLLECTIONS_TO_MIGRATE = []  # e.g. ["form_collection", "analysis_collection"] — only used if MIGRATE_ALL = False

# Auto-delete existing new collections (set to False for manual confirmation)
AUTO_DELETE_EXISTING = False
# ===================================


def _get_default_form_vectors_config():
    """Default config for form/demo collection: dense + sparse (matches insert.py)."""
    return {
        "dense": qmodels.VectorParams(size=768, distance=qmodels.Distance.COSINE),
        "sparse": qmodels.VectorParams(size=50000, distance=qmodels.Distance.COSINE),
    }


def _get_default_analysis_vectors_config():
    """Default config for analysis collection: dense only (matches insert_analysis.py)."""
    return {
        "dense": qmodels.VectorParams(size=768, distance=qmodels.Distance.COSINE),
    }


def _vectors_config_for_collection(collection_name: str, old_info=None):
    """Get vectors_config from existing collection or default for this project."""
    if old_info is not None and hasattr(old_info, "config") and old_info.config and hasattr(old_info.config, "params"):
        return old_info.config.params.vectors
    # Default by name: form/demo has dense+sparse, analysis has dense only
    if "analysis" in (collection_name or "").lower():
        return _get_default_analysis_vectors_config()
    return _get_default_form_vectors_config()


def migrate_collection(client: QdrantClient, old_name: str, new_name: str, host: str, port: int) -> bool:
    """
    Migrate a single collection from old_name to new_name.
    Returns True if successful, False otherwise.
    """
    print(f"\n{'='*60}")
    print(f"🔄 Migrating: {old_name} → {new_name}")
    print(f"{'='*60}")

    try:
        # Step 1: Check if old collection exists
        print(f"\n📊 Step 1: Checking old collection '{old_name}'...")
        old_collection_exists = False
        old_count = 0
        old_info = None

        try:
            old_info = client.get_collection(collection_name=old_name)
            old_count = client.count(collection_name=old_name).count
            old_collection_exists = True
            print(f"   ✅ Found {old_count} records")
        except Exception as e:
            print(f"   ⚠️ Old collection '{old_name}' not found: {e}")
            print(f"   ℹ️ Will create new collection with default config...")
            old_collection_exists = False

        is_empty = old_count == 0

        # Step 2: Create snapshot (skip if empty or doesn't exist)
        snapshot = None
        if old_collection_exists and not is_empty:
            print(f"\n📸 Step 2: Creating snapshot...")
            try:
                snapshot = client.create_snapshot(collection_name=old_name)
                print(f"   ✅ Snapshot created: {snapshot.name}")
            except Exception as e:
                print(f"   ❌ Failed to create snapshot: {e}")
                return False
        else:
            print(f"\n📸 Step 2: Skipping snapshot (collection is empty or missing)")

        # Step 3: Get vectors config
        print(f"\n⚙️ Step 3: Getting collection configuration...")
        vectors_config = _vectors_config_for_collection(old_name, old_info)
        if old_collection_exists:
            print(f"   ✅ Config retrieved from existing collection")
        else:
            print(f"   ✅ Using default config for this project")

        # Step 4: Check/Create new collection
        print(f"\n🆕 Step 4: Setting up new collection '{new_name}'...")
        try:
            existing_collection = client.get_collection(new_name)
            existing_count = client.count(new_name).count
            print(f"   ⚠️ Collection already exists with {existing_count} records")

            should_delete = AUTO_DELETE_EXISTING
            if not AUTO_DELETE_EXISTING:
                user_input = input(f"   Delete existing '{new_name}' and recreate? (yes/no): ").strip().lower()
                should_delete = user_input == "yes"

            if should_delete:
                client.delete_collection(new_name)
                print(f"   🗑️ Deleted existing collection")
                client.create_collection(
                    collection_name=new_name,
                    vectors_config=vectors_config,
                )
                print(f"   ✅ New collection created")
            else:
                print(f"   ℹ️ Skipping (user chose not to delete)")
                return False
        except Exception:
            # Collection doesn't exist, create it
            client.create_collection(
                collection_name=new_name,
                vectors_config=vectors_config,
            )
            print(f"   ✅ New collection created")

        # Step 5: Restore snapshot (skip if empty or doesn't exist)
        restore_success = False
        if not old_collection_exists or is_empty:
            print(f"\n♻️ Step 5: Skipping data restore (collection is empty or missing)")
            restore_success = True
        else:
            print(f"\n♻️ Step 5: Restoring data from snapshot...")
            try:
                snapshot_path = f"http://{host}:{port}/collections/{old_name}/snapshots/{snapshot.name}"
                client.recover_snapshot(
                    collection_name=new_name,
                    location=snapshot_path,
                )
                print(f"   ✅ Data restored using HTTP path")
                restore_success = True
            except Exception as e1:
                print(f"   ⚠️ Snapshot restore failed: {str(e1)[:100]}")
                try:
                    from qdrant_client.http.models import SnapshotRecover
                    client.recover_from_snapshot(
                        collection_name=new_name,
                        snapshot_name=snapshot.name,
                        source_collection_name=old_name,
                    )
                    print(f"   ✅ Data restored using alternative method")
                    restore_success = True
                except Exception as e2:
                    print(f"   ⚠️ Alternative restore failed: {str(e2)[:100]}")
                    print(f"   🔄 Falling back to manual copy...")

        # Step 6: Manual copy fallback
        if not restore_success and not is_empty:
            print(f"\n📋 Step 6: Manual copy fallback...")
            try:
                offset = None
                batch_size = 100
                total_copied = 0

                while True:
                    records, next_offset = client.scroll(
                        collection_name=old_name,
                        limit=batch_size,
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,
                    )

                    if not records:
                        break

                    client.upsert(
                        collection_name=new_name,
                        points=records,
                    )

                    total_copied += len(records)
                    progress_pct = (total_copied / old_count) * 100
                    print(f"   Progress: {total_copied}/{old_count} records ({progress_pct:.1f}%)")

                    offset = next_offset
                    if offset is None:
                        break

                print(f"   ✅ Manual copy complete: {total_copied} records")
                restore_success = True
            except Exception as e_manual:
                print(f"   ❌ Manual copy failed: {e_manual}")
                import traceback
                traceback.print_exc()
                return False

        # Step 7: Verify
        print(f"\n🔍 Step 7: Verifying migration...")
        try:
            new_count = client.count(collection_name=new_name).count
            print(f"   Old collection: {old_count} records")
            print(f"   New collection: {new_count} records")

            if old_count == new_count or (is_empty and new_count == 0):
                if is_empty:
                    print(f"\n   ✅ SUCCESS! Empty collection created and ready.")
                else:
                    print(f"\n   ✅ SUCCESS! Migration complete.")
                print(f"\n   ⚠️ REMINDER: Update .env with new collection names, then delete old collection if desired.")
                return True
            else:
                print(f"\n   ⚠️ WARNING! Counts don't match (Old: {old_count}, New: {new_count})")
                return False
        except Exception as e:
            print(f"   ❌ Verification failed: {e}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main migration function."""
    print("=" * 60)
    print("🚀 Qdrant Collection Migration — ai-evaluator-demo-trials-")
    print("=" * 60)

    if not QDRANT_LOCAL_URI:
        print("\n❌ QDRANT_LOCAL_URI not set. Set Qdrant_Localhost in .env")
        sys.exit(1)

    mappings = _build_collection_mappings()
    if not mappings:
        print("\n❌ No collection names in .env. Set Qdrant_Form and Qdrant_Analysis_Report.")
        sys.exit(1)

    try:
        if QDRANT_API_KEY:
            client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=60)
        else:
            client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=60)
        print(f"\n✅ Connected to Qdrant at {QDRANT_LOCAL_URI}")

        parsed_uri = urlparse(QDRANT_LOCAL_URI)
        qdrant_host = parsed_uri.hostname or "localhost"
        qdrant_port = parsed_uri.port or 6333
    except Exception as e:
        print(f"\n❌ Failed to connect to Qdrant: {e}")
        sys.exit(1)

    if MIGRATE_ALL:
        collections_to_migrate = list(mappings.keys())
        print(f"\n📋 Migrating ALL collections ({len(collections_to_migrate)} total)")
    else:
        collections_to_migrate = [c for c in COLLECTIONS_TO_MIGRATE if c and c in mappings]
        print(f"\n📋 Migrating SPECIFIC collections: {collections_to_migrate}")

    print(f"\n📝 Migration Plan:")
    for old_name in collections_to_migrate:
        new_name = mappings.get(old_name)
        if new_name:
            print(f"   • {old_name} → {new_name}")

    if not AUTO_DELETE_EXISTING:
        user_input = input(f"\nProceed with migration? (yes/no): ").strip().lower()
        if user_input != "yes":
            print("❌ Migration cancelled.")
            sys.exit(0)

    results = {}
    for old_name in collections_to_migrate:
        new_name = mappings.get(old_name)
        if not new_name:
            continue
        success = migrate_collection(client, old_name, new_name, qdrant_host, qdrant_port)
        results[old_name] = success

    print(f"\n{'='*60}")
    print(f"📊 Migration Summary")
    print(f"{'='*60}")

    successful = [n for n, ok in results.items() if ok]
    failed = [n for n, ok in results.items() if not ok]

    if successful:
        print(f"\n✅ Successful ({len(successful)}):")
        for name in successful:
            print(f"   • {name} → {mappings[name]}")
    if failed:
        print(f"\n❌ Failed ({len(failed)}):")
        for name in failed:
            print(f"   • {name} → {mappings[name]}")

    if not failed:
        print(f"\n🎉 All migrations completed.")
        print(f"\n⚠️ Next steps:")
        print(f"   1. Update .env: Qdrant_Form={PREFIX}form, Qdrant_Analysis_Report={PREFIX}analysis")
        print(f"   2. Restart the app and test.")
        print(f"   3. After verification, delete old collections in Qdrant if desired.")
    else:
        print(f"\n⚠️ Some migrations failed. Review errors above.")


if __name__ == "__main__":
    main()
