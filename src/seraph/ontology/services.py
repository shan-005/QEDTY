from pydantic import BaseModel,ConfigDict,Field
class Service(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    service_id:str=Field(min_length=1,max_length=256)
    name:str=Field(min_length=1,max_length=256)
    provider_entity_ids:tuple[str,...]=()
    criticality:float=Field(default=0.5,ge=0,le=1)
    geographic_scope:tuple[str,...]=()
    properties:dict[str,str]={}
