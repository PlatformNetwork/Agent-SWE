# rocicorp/mono-5590 (original PR)

rocicorp/mono (#5590): fix(zero-cache): fix cleanup of replica state after a non-disruptive resync

The non-disruptive resync logic leaves replication slots untouched while syncing a  new one, and then deletes older ones when the sync is complete. The logic incorrectly deleted _all_ other rows from the `replicas` metadata table, rather than only the older ones, as was done for replication slots.
