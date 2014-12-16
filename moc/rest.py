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

from werkzeug.wrappers import Request as WZRequest, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException
from werkzeug.local import Local, LocalManager

local = Local()
local_manager = LocalManager([local])

logger = logging.getLogger(__name__)

_url_map = Map()

from moc.functional import curry


class Request(WZRequest):
    """An extension of Werkzeug's Request object

    This adds convienience methods for a couple of important operations.
    """
    def body(self):
        """Return the body of the request, as a string."""
        return self.environ['wsgi.input'].read(self.content_length)


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


@curry
def route(path, methods, handler):
    _url_map.add(Rule(path, methods=methods, endpoint=handler))
    return handler


def get_request_body(request):
    return request.environ['wsgi.input'].read(request.content_length)


def request_handler(request):
    """Handle an http request.

    The parameter `request` must be an instance of werkzeug's `Request` class.
    The return value will be a werkzeug `Response` object.
    """
    adapter = _url_map.bind_to_environ(request.environ)
    try:
        handler, values = adapter.match()
        logger.debug('Recieved api call %s %r', handler.__name__, values)
        resp = handler(request=request, **values)
        logger.debug("completed call to api function %s, "
                     "response body: %r", handler.__name__, resp)
        return Response(resp, status=200)
    except HTTPException as e:
        return e
    except APIError as e:
        logger.debug('Invalid call to api function %s, raised exception: %r',
                     handler.__name__, e)
        return e.response()


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
