"""
Migration runner — executes numbered SQL files against the Supabase database.

Usage:
    python run_migrations.py          # run all pending migrations
    python run_migrations.py --reset  # drop everything and re-run from scratch
"""

import os
import sys
import glob
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ── Migration tracking table ────────────────────────────────────────────────
TRACKING_SQL = """
CREATE TABLE IF NOT EXISTS _migrations (
    id          SERIAL PRIMARY KEY,
    filename    VARCHAR(255) NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
"""


def get_connection():
    """Create a psycopg2 connection to Supabase."""
    return psycopg2.connect(DATABASE_URL)


def get_applied(conn) -> set[str]:
    """Return filenames of already-applied migrations."""
    cur = conn.cursor()
    cur.execute("SELECT filename FROM _migrations ORDER BY id;")
    return {row[0] for row in cur.fetchall()}


def apply_migration(conn, filepath: str):
    """Run a single .sql file inside a transaction."""
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()

    cur = conn.cursor()
    try:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO _migrations (filename) VALUES (%s);",
            (filename,),
        )
        conn.commit()
        print(f"  ✓ Applied: {filename}")
    except Exception as e:
        conn.rollback()
        print(f"  ✗ FAILED:  {filename} → {e}")
        raise


def reset_database(conn):
    """Drop all user tables and re-create the tracking table."""
    cur = conn.cursor()
    cur.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename != '_migrations'
            ) LOOP
                EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
            -- also drop views
            FOR r IN (
                SELECT viewname FROM pg_views
                WHERE schemaname = 'public'
            ) LOOP
                EXECUTE 'DROP VIEW IF EXISTS public.' || quote_ident(r.viewname) || ' CASCADE';
            END LOOP;
        END $$;
    """)
    cur.execute("DROP TABLE IF EXISTS _migrations CASCADE;")
    conn.commit()
    print("  ⟳ Database reset complete.")


def main():
    reset_mode = "--reset" in sys.argv

    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

    if not files:
        print("No migration files found in ./migrations/")
        return

    conn = get_connection()

    if reset_mode:
        print("\n── Resetting database ──")
        reset_database(conn)

    # Ensure tracking table exists
    cur = conn.cursor()
    cur.execute(TRACKING_SQL)
    conn.commit()

    applied = get_applied(conn)
    pending = [f for f in files if os.path.basename(f) not in applied]

    if not pending:
        print("\n✓ All migrations already applied. Nothing to do.")
    else:
        print(f"\n── Running {len(pending)} migration(s) ──")
        for filepath in pending:
            apply_migration(conn, filepath)
        print("\n✓ All migrations applied successfully.")

    conn.close()


if __name__ == "__main__":
    main()
