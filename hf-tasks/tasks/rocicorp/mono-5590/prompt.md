# rocicorp/mono-5590

Fix non-disruptive resync cleanup so replica metadata is retained correctly. After a resync, remove only outdated replica state entries rather than deleting all replica metadata. Ensure replication slot cleanup remains scoped to older entries and that current replica state is preserved.
