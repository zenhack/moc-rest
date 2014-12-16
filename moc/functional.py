# Copyright 2014 Massachusetts Open Cloud Contributors (see AUTHORS).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module ``functional`` provides support for functional programming idioms."""

import inspect
from functools import wraps, partial


def _curryN(n, f):
    """Helper for the implementation of ``curry``.

    ``_curryN(n, f)`` returns a function whose first ``n`` arguments are
    curried. i.e. the function will be called directly after ``n`` elements
    are supplied. If more arguments are needed, this will result in an error.
    """
    def wrapper(*args, **kwargs):
        count = len(args)
        if count == n:
            return f(*args, **kwargs)
        else:
            return _curryN(n - count, partial(f, *args, **kwargs))
    return wrapper


def curry(f):
    """Curry returns a curried version of ``f``.

    A curried function may be called with fewer arguments than required by the
    uncurried version, in which case the return value will be a a new function
    which does not require the arguments which were supplied. For example::

        >>> def sum3(x, y, z):
        ...    return x + y + z
        >>> curried_sum3 = curry(sum3)
        >>> curried_sum3(1, 2, 3)
        6
        >>> type(curried_sum3(1, 2))
        <type 'function'>
        >>> curried_sum3(1, 2)(3)
        6
        >>> curried_sum3(1)(2,3)
        6
        >>> curried_sum3(1)(2)(3)
        6

    Note that passing arguments by name to a curried function currently
    results in undefined behavior -- the semantics of this will likely be
    nailed down in the future. i.e. ``curried_sum3(x=1)`` is not allowed.
    """
    args, _, _, defaults = inspect.getargspec(f)
    if defaults is None:
        return wraps(f)(_curryN(len(args), f))
    else:
        return wraps(f)(_curryN(len(args) - len(defaults)), f)
