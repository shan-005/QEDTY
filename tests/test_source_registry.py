from seraph.sources.registry import SourceRegistry,SourceDefinition
from seraph.sources.base import SourceAdapter,SourceContext
class A(SourceAdapter):
 domain="test"
 def discover(self,context:SourceContext): return ()
def test_registry():
 r=SourceRegistry();r.register(SourceDefinition("x","x","test",A()));assert r.get("x").domain=="test"
