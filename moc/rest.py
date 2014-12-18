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
"""Module `rest` provides a wsgi application implementing a REST API.

The function `wsgi_handler` is the wsgi entry point to the app.

The decorator `rest_call` and the class `APIError` are the main things of
interest in this module.
"""
import logging
import json

from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule, parse_rule
from werkzeug.exceptions import HTTPException, InternalServerError
from werkzeug.local import Local, LocalManager


req_local = Local()
local_manager = LocalManager([req_local])

logger = logging.getLogger(__name__)

_url_map = Map()


class APIError(Exception):
    """An exception indicating an error that should be reported to the user.

    i.e. If such an error occurs in a rest API call, it should be reported as
    part of the HTTP response.
    """
    status_code = 400  # Bad Request

    def response(self):
        return Response(json.dumps({'type': self.__class__.__name__,
                                    'msg': self.message,
                                    }), status=self.status_code)


class ValidationError(APIError):
    """An exception indicating that the body of the request was invalid."""


def rest_call(method, path):
    """A decorator which registers an http mapping to a python api call.

    ``rest_call`` makes no modifications to the function itself.
    Arguments:

    path - the url-path to map the function to. The format is the same as for
           werkzeug's router (e.g. ``'/foo/<bar>/baz'``)
    method - the HTTP method for the api call (e.g. POST, GET...)

    For each of the path compontents specified in ``path``, the decorated
    function must have an argument by the same name. In addition, the function
    must accept an argument ``request_body``, which will be the body of the
    request (as a string).

    For example, given:

        @rest_call('POST', '/some-url/<bar>/<baz>')
        def foo(bar, baz, request_body):
            pass

    When a POST request to /some-url/*/* occurs, ``foo`` will be invoked
    with its bar and baz arguments pulled from the url, and ``request_body``
    will be the body of the request. So:

        POST /some-url/alice/bob HTTP/1.1
        <headers...>

        {"quux": "eve"}

    Will invoke ``foo('alice', 'bob', '{"quux": "eve"}')``.

    If the function raises an `APIError`, the error will be reported to the
    client with the exception's status_code attribute as the return status, and
    a json object such as:

        {
            "type": "MissingArgumentError",
            "msg": "The required argument FOO was not supplied."
        }

    as the body, i.e. `type` will be the type of the exception, and `msg`
    will be a human-readable error message.
    """
    def register(f):
        _url_map.add(Rule(path, endpoint=f, methods=[method]))
        return f
    return register


def request_handler(request):
    """Handle an http request.

    The parameter `request` must be an instance of werkzeug's `Request` class.
    The return value will be a werkzeug `Response` object.
    """
    adapter = _url_map.bind_to_environ(request.environ)
    try:
        f, values = adapter.match()

        request_handle = request.environ['wsgi.input']
        if request.content_length is None:
            # content length is supplied by the client, and it can be absent.
            # If it is, we assume there is no body.
            values['request_body'] = ''
        else:
            values['request_body'] = request_handle.read(request.content_length)

        logger.debug('Recieved api call %s(**%r)', f.__name__, values)
        response_body = f(**values)
        if not response_body:
            response_body = ""
        logger.debug("completed call to api function %s, "
                     "response body: %r", f.__name__, response_body)
        return Response(response_body, status=200)
    except APIError, e:
        # TODO: We're getting deprecation errors about the use of e.message. We
        # should figure out what the right way to do this is.
        logger.debug('Invalid call to api function %s, raised exception: %r',
                     f.__name__, e)
        return e.response()
    except HTTPException, e:
        return e


@local_manager.middleware
def wsgi_handler(environ, start_response):
    """The wsgi entry point to the API."""
    response = request_handler(Request(environ))
    return response(environ, start_response)

def serve(debug=True):
    """Start an http server running the API.

    This is intended for development purposes *only* -- as such the default is
    to turn on the debugger (which allows arbitrary code execution from the
    client!) and configure the server to automatically restart when changes are
    made to the source code. The `debug` parameter can be used to change this
    behavior.
    """
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', 5000, wsgi_handler,
               use_debugger=debug,
               use_reloader=debug)
