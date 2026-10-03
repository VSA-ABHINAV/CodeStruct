"""Metadata extraction fixture."""

import os, sys as system
from ..other import duplicate as other_duplicate
from . import duplicate
from package.tools import helper as aliased_helper, second


@register("service")
class Service(Base, mixins.Named["service"]):
    """A decorated class."""

    class Nested:
        pass

    @classmethod
    def method(cls, value: int = 1, *args, flag=True, **kwargs) -> str:
        """A method with practical parameter forms."""

        direct(value)
        client.send(value)
        package.client.send(value)
        factory().service.run()

        def local(item):
            nested_call(item)

        return str(value)

    async def async_method(self):
        await async_call()


@decorate
async def async_function(first, /, second: str = "x", *, option=None):
    async_inner()


def outer(positional_only, /, regular=1, *items, named, optional=False, **extras):
    def inner():
        inner_call()

    return inner

