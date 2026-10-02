"""Base class shared by every domain model."""

from typing import Self

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Immutable, closed-schema base model.

    Domain objects are values: they are frozen, reject unknown fields, and validate on
    construction so an invalid object can never exist. Updates go through :meth:`revalidated`
    (or ``with_*`` helpers built on it), which re-runs every validator.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        str_strip_whitespace=True,
    )

    def revalidated(self, **changes: object) -> Self:
        """Return a copy with ``changes`` applied and all validators re-run."""
        data = self.model_dump()
        for name in type(self).model_computed_fields:
            data.pop(name, None)
        return type(self).model_validate({**data, **changes})
