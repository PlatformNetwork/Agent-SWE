# mirumee/ariadne-1283 (original PR)

mirumee/ariadne (#1283): refactor!: remove deprecated apollo tracing, opentracing, and extend_federated_schema



### What Was Removed

| Removed Item | Location (Before) |
|--------------|-------------------|
| **Apollo Tracing extension** | `ariadne.contrib.tracing.apollotracing` (e.g., `ApolloTracingExtension`, `apollo_tracing_extension()`) |
| **OpenTracing extension** | `ariadne.contrib.tracing.opentracing` (e.g., `OpenTracingExtension`, `opentracing_extension()`) |
| **extend_federated_schema() function** | `ariadne.contrib.federation.schema.extend_federated_schema()` |
| **Optional extra** | `tracing = ["opentracing"]` in `pyproject.toml` (and `opentracing` test dependency) |
| **Documentation** | `docs/02-Monitoring/02-open-tracing.md`, `docs/02-Monitoring/03-apollo-tracing.md` |

**Note:** Both OpenTracing and Apollo Tracing are archived projects. OpenTracing merged into OpenTelemetry, and Apollo Tracing is deprecated in favor of OpenTelemetry.
---

### What You Need to Change

#### 1. If you used `extend_federated_schema()`

Replace it with `graphql.extend_schema()` directly (same functionality, from `graphql-core`):

# Before
```
from ariadne.contrib.federation.schema import extend_federated_schema
schema = extend_federated_schema(schema, document_ast, assume_valid=..., assume_valid_sdl=...)
```
# After
```
from graphql import extend_schema
schema = extend_schema(schema, document_ast, assume_valid=..., assume_valid_sdl=...)
```

<!-- This is an auto-generated comment: release notes by coderabbit.ai -->

## Summary by CodeRabbit

* **Chores**
  * Removed ApolloTracingExtension and OpenTracingExtension tracing implementations
  * Removed deprecated EnumType.bind_to_default_values and extend_federated_schema methods
  * Removed opentracing dependency

* **Documentation**
  * Removed OpenTracing and Apollo Tracing integration guides

* **Tests**
  * Removed test suites for removed tracing extensions

<!-- end of auto-generated comment: release notes by coderabbit.ai -->
