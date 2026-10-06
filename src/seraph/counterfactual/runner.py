from .engine import CounterfactualEngine
def run_many(engine:CounterfactualEngine,shock,entity_id,interventions):return tuple(engine.compare(shock,entity_id,i) for i in interventions)
