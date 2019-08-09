# util files are an antipattern imo, but python just doesn't have this
class AttributeReference:

    def __init__(self, objekt, attribute):
        self.objekt = objekt
        self.attribute = attribute

    def __repr__(self):
        # uses hypothetical c-style & operator
        return '&' + repr(self.objekt) + '.' + self.attribute

    def __eq__(self, other):
        if not isinstance(other, AttributeReference):
            return NotImplemented
        return (self.objekt, self.attribute) == (other.objekt, other.attribute)

    def __hash__(self):
        return hash((self.objekt, self.attribute))

    def set(self, value):
        setattr(self.objekt, self.attribute, value)

    def get(self):
        return getattr(self.objekt, self.attribute)
