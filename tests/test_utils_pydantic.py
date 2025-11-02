import pytest
from urllib.parse import urlparse
from pydantic import ValidationError
from pydantic import TypeAdapter

from tendril.utils.pydantic import (
    TendrilTBase,
    TendrilTBaseModel,
    TendrilTORMModel,
    StrHttpUrl,
)


# ---------------------------------------------------------------------
#  Base model configuration behavior
# ---------------------------------------------------------------------

def test_tendril_base_model_config_consistency():
    """Ensure that TendrilTBase sets expected model_config flags."""
    assert TendrilTBase.model_config["validate_by_name"] is True
    assert TendrilTBase.model_config["arbitrary_types_allowed"] is True
    assert TendrilTBase.model_config["populate_by_name"] is True


def test_tendril_orm_model_extends_base_config():
    """Verify that ORM model extends base configuration and enables from_attributes."""
    base_config = TendrilTBase.model_config
    orm_config = TendrilTORMModel.model_config

    for key, val in base_config.items():
        assert key in orm_config
        assert orm_config[key] == val

    assert orm_config["from_attributes"] is True


def test_tendril_base_model_inheritance_behavior():
    """Ensure subclasses of TendrilTBase inherit configuration."""
    class Example(TendrilTBase):
        a: int

    example = Example(a=1)
    assert example.a == 1
    assert "populate_by_name" in Example.model_config


# ---------------------------------------------------------------------
#  StrHttpUrl validation and behavior
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    [
        "https://example.com",
        "http://127.0.0.1",
        "https://sub.domain.tld/path?query=1",
    ],
)
def test_str_http_url_valid_inputs(value):
    """Ensure valid URLs pass validation and result in StrHttpUrl instances."""
    validated = StrHttpUrl(value)
    assert isinstance(validated, StrHttpUrl)
    assert str(validated) == value
    assert repr(validated).startswith("StrHttpUrl(")
    assert ("example" in repr(validated)
            or "127.0.0.1" in repr(validated)
            or "sub.domain.tld" in repr(validated))


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/",
        "http://127.0.0.1/",
        "https://sub.domain.tld/path?query=1",
    ],
)
def test_str_http_url_valid_via_adapter(value):
    ta = TypeAdapter(StrHttpUrl, config={"arbitrary_types_allowed": True})
    v = ta.validate_python(value)
    assert isinstance(v, str)
    assert (urlparse(v) == urlparse(value))

@pytest.mark.parametrize(
    "invalid",
    [
        "not a url",
        "example.com",  # missing scheme
        "ftp://example.com",  # not http/https
        "http//missing-colon.com",
        "",
        1234,
    ],
)
def test_str_http_url_invalid_via_adapter(invalid):
    ta = TypeAdapter(StrHttpUrl, config={"arbitrary_types_allowed": True})
    try:
        ta.validate_python(invalid)
        assert False, f"Expected ValidationError for: {invalid!r}"
    except ValidationError:
        pass


def test_str_http_url_json_schema_structure():
    """Ensure generated JSON schema is string/uri type."""
    schema = StrHttpUrl.__get_pydantic_json_schema__(
        core_schema=None,
        handler=lambda s: {"type": "string"}
    )
    assert schema["type"] == "string"
    assert schema["format"] == "uri"


def test_str_http_url_validation_through_model():
    """Ensure StrHttpUrl works as a Pydantic field inside a model."""
    class Model(TendrilTBaseModel):
        picture: StrHttpUrl

    model = Model(picture="https://example.org/avatar.png")
    assert isinstance(model.picture, StrHttpUrl)
    assert str(model.picture) == "https://example.org/avatar.png"

    # Invalid URL should raise
    with pytest.raises(ValidationError):
        Model(picture="invalid_url")


def test_str_http_url_accepts_itself():
    """Ensure passing an existing StrHttpUrl doesn’t double-validate or break."""
    s = StrHttpUrl("https://good.example")
    again = StrHttpUrl(s)
    assert again == s
    assert isinstance(again, StrHttpUrl)


# ---------------------------------------------------------------------
#  Integration: ORM + StrHttpUrl
# ---------------------------------------------------------------------

def test_orm_model_with_strhttpurl_field():
    """Ensure ORM model with StrHttpUrl field supports from_attributes=True."""
    class Dummy:
        def __init__(self):
            self.picture = "https://example.com/x.png"

    class ORMModel(TendrilTORMModel):
        picture: StrHttpUrl

    # using from_attributes
    obj = Dummy()
    instance = ORMModel.model_validate(obj, from_attributes=True)
    assert isinstance(instance.picture, StrHttpUrl)
    assert str(instance.picture) == "https://example.com/x.png"
