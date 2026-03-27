import importlib.util
import sys
import types
from pathlib import Path

TARGET_PATH = Path(
    "libs/azure/functions/blueprints/esquire/audiences/builder/activities/fetchAudience.py"
)


class Field:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


class QueryStub:
    def __init__(self, model):
        self.model = model

    def options(self, *args, **kwargs):
        return self

    def where(self, *args, **kwargs):
        return self


class ResultStub:
    def __init__(self, audience):
        self.Audience = audience

    def one_or_none(self):
        return self if self.Audience is not None else None

    def __bool__(self):
        return self.Audience is not None


class SessionStub:
    def __init__(self, audience):
        self._audience = audience

    def execute(self, query):
        return ResultStub(self._audience)

    def close(self):
        return None


def install_stubs(provider):
    def make_package(name):
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
        return module

    for pkg in [
        "azure",
        "azure.durable_functions",
        "libs",
        "libs.azure",
        "libs.azure.functions",
        "libs.azure.functions.blueprints",
        "libs.azure.functions.blueprints.esquire",
        "libs.azure.functions.blueprints.esquire.audiences",
        "libs.azure.functions.blueprints.esquire.audiences.builder",
        "libs.azure.functions.blueprints.esquire.audiences.builder.activities",
        "libs.azure.functions.blueprints.esquire.audiences.builder.utils",
        "libs.data",
        "libs.data.structured",
        "libs.data.structured.sqlalchemy",
        "libs.data.structured.sqlalchemy.utils",
        "sqlalchemy",
        "sqlalchemy.orm",
    ]:
        make_package(pkg)

    durable = sys.modules["azure.durable_functions"]

    class Blueprint:
        def activity_trigger(self, input_name=None):
            def decorator(fn):
                return fn

            return decorator

    durable.Blueprint = Blueprint

    utils = sys.modules["libs.azure.functions.blueprints.esquire.audiences.builder.utils"]

    def jsonlogic_to_sql(data):
        return f"SQL({data})"

    def enforce_bindings():
        return None

    utils.jsonlogic_to_sql = jsonlogic_to_sql
    utils.enforce_bindings = enforce_bindings

    data_mod = sys.modules["libs.data"]

    def from_bind(name):
        return provider

    def register_binding(*args, **kwargs):
        return None

    data_mod.from_bind = from_bind
    data_mod.register_binding = register_binding

    sqlalchemy_mod = sys.modules["sqlalchemy"]

    def select(model):
        return QueryStub(model)

    sqlalchemy_mod.select = select

    sqlalchemy_orm = sys.modules["sqlalchemy.orm"]

    def lazyload(arg):
        return f"lazyload:{arg}"

    sqlalchemy_orm.lazyload = lazyload
    sqlalchemy_orm.Session = SessionStub

    utils_mod = sys.modules["libs.data.structured.sqlalchemy.utils"]

    def _find_relationship_key(source, target, uselist=False):
        if target.__name__ == "AdvertiserModel":
            return "advertiser"
        if target.__name__ == "TargetingDataSourceModel":
            return "targetingDataSource"
        return "unknown"

    utils_mod._find_relationship_key = _find_relationship_key


def load_module():
    unique_name = f"fetchAudience_{id(object())}"
    spec = importlib.util.spec_from_file_location(unique_name, TARGET_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_provider(audience):
    class AudienceModel:
        id = Field("id")

    class AdvertiserModel:
        pass

    class TargetingDataSourceModel:
        pass

    AudienceModel.advertiser = "advertiser"
    AudienceModel.targetingDataSource = "targetingDataSource"

    class Provider:
        models = {
            "keystone": {
                "Audience": AudienceModel,
                "Advertiser": AdvertiserModel,
                "TargetingDataSource": TargetingDataSourceModel,
            }
        }

        def connect(self):
            return SessionStub(audience)

    return Provider()


def build_audience(**attrs):
    class Audience:
        pass

    aud = Audience()
    for key, value in attrs.items():
        setattr(aud, key, value)

    class Advertiser:
        freewheel = "fw"
        meta = {"tier": "gold"}
        xandr = "xndr"

    class TargetingDataSource:
        id = "tds-42"
        dataType = "geo"

    aud.advertiser = Advertiser()
    aud.targetingDataSource = TargetingDataSource()
    return aud


def run_activity(audience):
    provider = build_provider(audience)
    install_stubs(provider)
    module = load_module()
    ingress = {"id": "aud-123", "extra": "keep"}
    return module.activity_esquireAudienceBuilder_fetchAudience(ingress)


def test_demographic_filter_key_and_sql_conversion():
    audience = build_audience(
        status="active",
        rebuildSchedule="weekly",
        TTL_Length=7,
        TTL_Unit="days",
        dataFilter={"==": ["age", 25]},
        demographicFilter={"segment": "sports"},
        demographicsFilter={"segment": "legacy"},
        processing="queued",
    )
    result = run_activity(audience)

    assert result["demographicFilter"] == {"segment": "sports"}
    assert "demographicsFilter" not in result
    assert result["dataFilter"] == "SQL({'==': ['age', 25]})"
    assert result["dataFilterRaw"] == {"==": ["age", 25]}
    assert result["advertiser"]["freewheel"] == "fw"


def test_demographic_filter_missing_returns_none():
    audience = build_audience(
        status="inactive",
        rebuildSchedule=None,
        TTL_Length=None,
        TTL_Unit=None,
        dataFilter=None,
        demographicsFilter={"segment": "legacy"},
        processing=None,
    )
    result = run_activity(audience)

    assert "demographicFilter" in result
    assert result["demographicFilter"] is None
    assert "demographicsFilter" not in result
    assert result["dataFilter"] is None
    assert result["dataFilterRaw"] is None
