import typing


T = typing.TypeVar('T')


# util files are an antipattern imo, but python just doesn't have this
class AttributeReference(typing.Generic[T]):

    def __init__(self, objekt: object, attribute: str):
        self.objekt = objekt
        self.attribute = attribute

    def __repr__(self) -> str:
        # uses hypothetical c-style & operator
        return '&' + repr(self.objekt) + '.' + self.attribute

    def __eq__(self, other: typing.Any) -> typing.Union[
            bool, 'NotImplemented']:
        if not isinstance(other, AttributeReference):
            return NotImplemented
        return (self.objekt, self.attribute) == (other.objekt, other.attribute)

    def __hash__(self) -> int:
        return hash((self.objekt, self.attribute))

    def set(self, value: T) -> None:
        setattr(self.objekt, self.attribute, value)

    def get(self) -> T:
        return typing.cast(T, getattr(self.objekt, self.attribute))
