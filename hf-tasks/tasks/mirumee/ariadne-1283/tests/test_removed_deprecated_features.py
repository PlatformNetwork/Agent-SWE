import importlib
import sys

import pytest
from graphql import build_schema, extend_schema, parse


def test_apollo_tracing_module_removed():
    with pytest.raises(ModuleNotFoundError) as excinfo:
        importlib.import_module("ariadne.contrib.tracing.apollotracing")

    assert excinfo.value.name == "ariadne.contrib.tracing.apollotracing"
    assert "ariadne.contrib.tracing.apollotracing" not in sys.modules


def test_opentracing_module_removed():
    with pytest.raises(ModuleNotFoundError) as excinfo:
        importlib.import_module("ariadne.contrib.tracing.opentracing")

    assert excinfo.value.name == "ariadne.contrib.tracing.opentracing"
    assert "ariadne.contrib.tracing.opentracing" not in sys.modules


def test_extend_federated_schema_removed_and_extend_schema_supported():
    from ariadne.contrib.federation import schema as federation_schema

    assert not hasattr(federation_schema, "extend_federated_schema")

    base_schema = build_schema("type Query { hello: String }")
    extension_ast = parse("extend type Query { status: Boolean }")
    extended_schema = extend_schema(base_schema, extension_ast)

    assert "status" in extended_schema.get_type("Query").fields
