# sidequery/sidemantic-84

Ensure temporal values in query results are serialized to ISO string formats so JSON responses from query endpoints do not fail. Prevent infinite loops when computing model hierarchy paths by detecting cycles in parent references and handling malformed loops safely. Update SQL filter validation to use the correct sqlglot expression type for ALTER statements in the current library version.
