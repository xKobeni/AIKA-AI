import argparse

from database.db import engine
from database.migrations import MigrationBlockedError, MigrationRunner


def main():
    parser = argparse.ArgumentParser(description="AIKA database migration manager")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show migration status")
    mode.add_argument("--dry-run", action="store_true", help="List pending migrations")
    mode.add_argument("--apply", action="store_true", help="Apply pending migrations")
    args = parser.parse_args()

    runner = MigrationRunner(engine)
    try:
        if args.apply:
            migrations = runner.migrate()
            label = "Applied"
        elif args.dry_run:
            migrations = runner.migrate(dry_run=True)
            label = "Pending"
        else:
            status = runner.status()
            print(
                f"Current schema version: {status['current_version']} / "
                f"{status['latest_version']}"
            )
            migrations = status["pending"]
            label = "Pending"

        if migrations:
            for migration in migrations:
                print(f"{label} {migration.version}: {migration.name}")
        else:
            print("No pending migrations.")
        return 0
    except MigrationBlockedError as exc:
        print(f"Migration blocked: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
