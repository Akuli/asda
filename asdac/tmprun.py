import abc

from . import tokenizer, raw_ast, chef


class AsdaObject(metaclass=abc.ABCMeta):
    pass


class String(AsdaObject):

    def __init__(self, python_string):
        self.python_string = python_string


class Function(AsdaObject):

    @abc.abstractmethod
    def run(self, args):
        pass


class PrintFunction(Function):

    def run(self, args):
        [string] = args
        print(string.python_string)


class FunctionDefinedInAsda(AsdaObject):

    def __init__(self, body, definer_runner):
        self.body = body
        self.definer_runner = definer_runner

    def run(self, args):
        assert not args
        runner = Runner(self.definer_runner)
        for statement in self.body:
            runner.execute(statement)


class Runner:

    def __init__(self, parent_runner):
        self.parent_runner = parent_runner
        if parent_runner is None:
            self.level = 0
        else:
            self.level = parent_runner.level + 1
        self.local_vars = {}

    def evaluate(self, ast):
        if isinstance(ast, chef.CreateFunction):
            return FunctionDefinedInAsda(ast.body, self)

        if isinstance(ast, chef.LookupVar):
            level_difference = self.level - ast.level
            assert level_difference >= 0

            runner = self
            for lel in range(level_difference):
                runner = runner.parent_runner
            return runner.local_vars[ast.varname]

        if isinstance(ast, chef.StrConstant):
            return String(ast.python_string)

        assert False, ast

    def execute(self, ast):
        if isinstance(ast, chef.CreateLocalVar):
            self.local_vars[ast.name] = self.evaluate(ast.initial_value)
        elif isinstance(ast, chef.CallFunction):
            self.evaluate(ast.function).run([self.evaluate(arg) for arg in ast.args])
        else:
            assert False, ast


code = '''
print("hello world")
'''

tokens = tokenizer.tokenize('test file', code)
raw_ast = raw_ast.parse(tokens)
cooked_ast = chef.cook('test file', raw_ast)
r = Runner(None)
r.local_vars['print'] = PrintFunction()
for asd in cooked_ast:
    r.execute(asd)
