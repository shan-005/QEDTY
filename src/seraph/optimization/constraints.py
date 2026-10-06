from seraph.scenarios.models import Intervention
def feasible(intervention:Intervention,budget_usd:float)->bool:return intervention.cost_usd<=budget_usd
