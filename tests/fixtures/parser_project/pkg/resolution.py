from .base import ImportedBase as BaseAlias, imported_function as imported
import pkg.base as base_alias


class LocalClass:
    def method(self):
        return None

    def invoke(self):
        self.method()
        LocalClass()

    @classmethod
    def invoke_class(cls):
        cls.method()


class Child(BaseAlias):
    pass


class CycleA(CycleB):
    pass


class CycleB(CycleA):
    pass


def local_function():
    return None


def caller():
    local_function()
    local_function()
    imported()
    base_alias.imported_function()
    dynamic.factory().run()


def mutual_a():
    mutual_b()


def mutual_b():
    mutual_a()


def ambiguous():
    return 1


def ambiguous():
    return 2


def ambiguous_caller():
    ambiguous()


def outer_scope():
    def inner_scope():
        return None

    inner_scope()
