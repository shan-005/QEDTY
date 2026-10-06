from pydantic import BaseModel,ConfigDict,Field
class DataQuality(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    completeness:float=Field(default=1,ge=0,le=1); timeliness:float=Field(default=1,ge=0,le=1); spatial_accuracy:float=Field(default=1,ge=0,le=1); semantic_accuracy:float=Field(default=1,ge=0,le=1); lineage_strength:float=Field(default=1,ge=0,le=1)
    @property
    def composite(self)->float:return sum((self.completeness,self.timeliness,self.spatial_accuracy,self.semantic_accuracy,self.lineage_strength))/5
