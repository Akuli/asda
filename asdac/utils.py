# util files are an antipattern imo, but python just doesn't have this
class AttributeReference:

    def __init__(self, objekt, attribute):
        self._objekt = objekt
        self._attribute = attribute

    def __repr__(self):
        # uses hypothetical c-style & operator
        return '&' + repr(self._objekt) + '.' + self._attribute

    def __eq__(self, other):
        if not isinstance(other, AttributeReference):
            return NotImplemented
        return ((self._objekt, self._attribute) ==
                (other._objekt, other._attribute))

    def set(self, value):
        setattr(self._objekt, self._attribute, value)

    def get(self):
        return getattr(self._objekt, self._attribute)
