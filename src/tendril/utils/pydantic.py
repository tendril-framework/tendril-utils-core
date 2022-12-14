


from pydantic import BaseModel


class TendrilTBaseModel(BaseModel):
    class Config:
        allow_population_by_field_name = True
