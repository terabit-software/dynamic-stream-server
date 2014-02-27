# coding: utf-8
import unittest
from dss.tools.pseudo_list import load


class LoadTest(unittest.TestCase):

    def run_dict(self, function, dct):
        for k, v in dct.items():

            if isinstance(v, type) and issubclass(v, BaseException):
                self.assertRaises(v, function, k)
            else:
                self.assertEqual(function(k), v)

    def test_numbers(self):
        self.run_dict(load, {
            '1': [1],
            '1 2 3': [1, 2, 3],
            '1, 2, 3': [1, 2, 3],
            '1 [2,], 3': [1, [2], 3],
            '1,,,2   3': [1, 2, 3],
        })

    def test_strings(self):
        self.run_dict(load, {
            'a': ['a'],
            'a b c': ['a', 'b', 'c'],
            'a, "b", c': ['a', 'b', 'c'],
            '"aaa", "b b" " c "': ["aaa", "b b", " c "],
            "'a''b''c'": ['a', 'b', 'c'],
        })

    def test_dict(self):
        self.run_dict(load, {
            '{1:2,3:4}': [{1: 2, 3: 4}],
            '{1: b , 2 : 3}': [{1: 'b', 2: 3}],
            '{"1": b , 2 : "3"}': [{'1': 'b', 2: '3'}],
            '{1:}': TypeError,
            '{:1}': TypeError,
        })
