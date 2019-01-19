from asdac import tokenizer


def tokenize(code):
    return list(tokenizer.tokenize('test file', code))


def test_automatic_trailing_newline():
    assert tokenize('let x = y') == tokenize('let x = y\n')
