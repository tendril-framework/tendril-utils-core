

from typing import Callable, Optional, Sequence, Any
from pydantic import BaseModel
from pydantic import HttpUrl, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class TendrilTBase(BaseModel):
    model_config = {
        "validate_by_name": True,
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }


class TendrilTBaseModel(TendrilTBase):
    """Standard Tendril model."""
    pass


class TendrilTORMModel(TendrilTBase):
    """ORM-compatible Tendril model."""
    model_config = {
        **TendrilTBase.model_config,
        "from_attributes": True,
    }


class StrHttpUrl(str):
    """
    Behaves like a plain string, but validates as a proper URL using Pydantic's HttpUrl.
    Accepts and outputs strings, while leveraging HttpUrl's URL validation.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        # Get HttpUrl to ensure its validation logic is loaded
        handler(HttpUrl)

        def validate(value: Any) -> "StrHttpUrl":
            if isinstance(value, StrHttpUrl):
                return value
            try:
                validated = HttpUrl(value)
            except Exception as e:
                raise ValueError(str(e)) from e
            return cls(str(validated))

        # Base schema for type information
        base_schema = core_schema.str_schema()

        # Wrap the base schema in our validator
        return core_schema.no_info_after_validator_function(
            function=validate,
            schema=base_schema,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        # Use the base schema but ensure it shows as a URI
        schema = handler(core_schema)
        schema.update(type="string", format="uri")
        return schema

    def __repr__(self) -> str:
        return f"StrHttpUrl({super().__str__()!r})"
