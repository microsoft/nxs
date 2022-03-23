from pydantic import BaseModel
from humps import camelize

# based on this tutorial:
# https://medium.com/analytics-vidhya/camel-case-models-with-fast-api-and-pydantic-5a8acb6c0eee

def to_camel(string):
    return camelize(string)

class DataModel(BaseModel):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
    
    pass
