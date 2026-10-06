from pydantic import BaseModel,ConfigDict,Field
class Flow(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    flow_id:str=Field(min_length=1,max_length=256)
    flow_type:str=Field(min_length=1,max_length=64)
    source_entity_id:str; target_entity_id:str
    quantity:float=Field(ge=0); unit:str=Field(min_length=1,max_length=64)
    period:str=Field(min_length=1,max_length=64)
    confidence:float=Field(default=1,ge=0,le=1)
    evidence_ids:tuple[str,...]=()
