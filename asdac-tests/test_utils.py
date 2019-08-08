import operator
import re

from asdac import utils


class Foo:
    pass


def test_attributereference_set_get_repr():
    foo = Foo()

    ref = utils.AttributeReference(foo, 'bar')
    ref.set('lol')
    assert foo.bar == ref.get() == 'lol'
    foo.bar = 'wat'
    assert foo.bar == ref.get() == 'wat'

    assert re.fullmatch(r'&<\w+\.Foo object at 0x[0-9a-f]+>\.bar',
                        repr(ref)) is not None


def check_equality(objects):
    # equality must be an equivalence relation
    for first in objects:
        assert first == first
        for second in objects:
            if first == second:
                assert second == first
            for third in objects:
                if first == second and second == third:
                    assert first == third


def test_attributereference_equality():
    a = Foo()
    b = Foo()
    abar = utils.AttributeReference(a, 'bar')
    abar2 = utils.AttributeReference(a, 'bar')
    bbar = utils.AttributeReference(b, 'bar')
    bbaz = utils.AttributeReference(b, 'baz')

    assert abar != 'lol'
    assert abar == abar
    assert abar == abar2
    assert abar1 != bbar
    assert bbar != bbaz

    check_equality([abar, abar2, bbar, bbaz])
