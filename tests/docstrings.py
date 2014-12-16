from moc import functional
import unittest
import doctest


class TestDocstrings(unittest.TestCase):

    def test_docstrings(self):
        doctest.testmod(functional, raise_on_error=True)
