# Rollback procedure

Keep the prior wheel/container and checksum plus a database backup taken before upgrade. Stop the candidate cleanly. If the candidate migrated the database, restore the verified backup before starting older code; application-only rollback is unsafe when the prior version cannot read the new schema. Do not attempt a destructive reverse migration.

Activate the previous isolated environment or image, restore the previous configuration, start on loopback, and verify readiness, project discovery, analysis, graph retrieval, and cache behavior. If database restoration fails, preserve both files and stop for operator review—never silently create an empty replacement or touch analyzed source.

Phase 14 exercises schema migration and backup restoration only with temporary databases. Production backup consistency and restore timing remain operator responsibilities.
