


from pydantic import BaseModel


class TendrilTBaseModel(BaseModel):
    class Config:
        allow_population_by_field_name = True


class TendrilTORMModel(BaseModel):
    class Config:
        allow_population_by_field_name = True
        orm_mode = True


