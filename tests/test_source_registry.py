from seraph.sources.base import SourceAdapter, SourceContext
from seraph.sources.registry import SourceDefinition, SourceRegistry


class A(SourceAdapter):
    domain = "test"

    def discover(self, context: SourceContext):
        return ()


def test_registry():
    r = SourceRegistry()
    r.register(SourceDefinition("x", "x", "test", A()))
    assert r.get("x").domain == "test"
