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
from moc import rest

from abc import ABCMeta, abstractmethod
import unittest
import json

from werkzeug.routing import Map
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder

# We don't directly use this, but unless we import it, the coverage tool
# complains and doesn't give us a report.
import pytest


class HttpTest(unittest.TestCase):
    """A test which excercises the http server.

    HttpTests run with no api functions registered to the http server yet;
    this lets us test the http-related code in an environment that is not
    constrained by our actual api.
    """

    def setUp(self):
        # We back up the old _url_map, and restore it in tearDown; this makes
        # it easy to be sure that we're not interfering with other tests:
        self.old_url_map = rest._url_map
        # We make ourselves an empty one for our test:
        rest._url_map = Map()

    def tearDown(self):
        rest._url_map = self.old_url_map


class HttpEquivalenceTest(object):
    """A test that ensures a particlar call to the api behaves the same over
    http and when called as a function. Subclasses must override `api_call`
    and `request`, and may also be interested in `api_setup` and
    `api_teardown`.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def api_call(self, request_body):
        """Invoke the api call directly."""

    @abstractmethod
    def request(self):
        """Return a request which will invoke the api call.

        The request should take the form of a WSGI v1.0 environment.
        Werkzeug's ``EnvironBuilder`` can be used to build a suitable
        environment.
        """

    def api_setup(self):
        """Setup routine to be run before each call to the api.

        This is conceptually similar to python's unittest setUp()
        method, but with each call to `api_call`, rather than the
        whole test.

        By default this is a noop; subclasses should override this if
        they need specific environments.
        """

    def api_teardown(self):
        """like `api_setup`, but tears things down after the call."""

    def test_equivalence(self):
        """Calling `api_call` directly should be the same as via http."""

        # First invoke the call over http. This should never raise exceptions.
        self.api_setup()
        req = Request(self.request())
        req_body = req.environ['wsgi.input'].read()
        req.environ['wsgi.input'].seek(0)
        resp = rest.request_handler(req)
        body = resp.get_data()
        self.api_teardown()

        # Now call it directly.
        try:
            self.api_setup()
            ret = self.api_call(req_body)
            assert resp.status_code == 200
            if ret == '':
                assert body == ''
            else:
                assert json.loads(body) == json.loads(ret)
        except rest.APIError, e:
            assert resp.status_code == e.status_code
            assert json.loads(body) == {'type': e.__class__.__name__,
                                        'msg': e.message,
                                        }
        finally:
            self.api_teardown()


class TestUrlArgs(HttpEquivalenceTest, HttpTest):
    """Test that arguments supplied in the url are passed correctly."""
    # The use of HTTPEquivalenceTest here is a bit weird; We're not actually
    # calling the api function from `api_call`. This is actually probably a
    # fairly common way to want to use the superclass; we should think about
    # whether the documented usage is necessarily the right idea.

    def setUp(self):
        HttpTest.setUp(self)

        @rest.rest_call('GET', '/func/<foo>/<bar>')
        def func(foo, bar, request_body):
            return json.dumps([foo, bar])

    def api_call(self, request_body):
        return json.dumps(['alice', 'bob'])

    def request(self):
        return EnvironBuilder(method='GET', path='/func/alice/bob').get_environ()


class TestBodyArgs(HttpEquivalenceTest, HttpTest):
    """Test that arguments supplied in the body are passed correctly."""

    def setUp(self):
        HttpTest.setUp(self)

        @rest.rest_call('POST', '/func/foo')
        def foo(request_body):
            obj = json.loads(request_body)
            return json.dumps([obj['bar'], obj['baz']])

    def api_call(self, request_body):
        return json.dumps(['bonnie', 'clyde'])

    def request(self):
        return EnvironBuilder(method='POST', path='/func/foo',
                              data=json.dumps({'bar': 'bonnie', 'baz': 'clyde'}),
                              content_type='application/json').get_environ()


class TestEquiv_basic_APIError(HttpEquivalenceTest, HttpTest):
    """Basic test to make sure the APIError handling code is excercised."""

    def setUp(self):
        HttpTest.setUp(self)

        @rest.rest_call('GET', '/some_error')
        def some_error(request_body):
            self.api_call(request_body)

    def api_call(self, request_body):
        raise rest.APIError("Basic test of the APIError code.")

    def request(self):
        return EnvironBuilder(method='GET', path='/some_error').get_environ()


def _is_error(resp, errtype):
    """Return True iff the Response `resp` represents an `errtype`.

    `resp` should be a response returned by `request_handler`.
    `errtype` should be a subclass of APIError.
    """
    try:
        return json.loads(resp.get_data())['type'] == errtype.__name__
    except:
        # It's possible that this response isn't even an error, in which case
        # the data may not parse as the above statement is expecting. Well,
        # it's not an error, so:
        return False
