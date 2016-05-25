#!/usr/bin/env python
# coding: utf-8
import glob
import unittest
import sys
from os import path


here = path.dirname(path.abspath(__file__))
root = path.dirname(here)
sys.path.insert(0, root)


def find(dir=''):

    files = glob.glob(path.join(here, dir, 'test*.py'))
    mod_name = ''
    if dir:
        mod_name = dir.replace('/', '.').replace('\\', '.')
        if mod_name:
            mod_name += '.'

    modules = [mod_name + path.splitext(path.basename(x))[0] for x in files]

    dirs = glob.glob(path.join(here, dir, '*tests'))
    for dir in dirs:
        modules.extend(find(path.relpath(dir, here)))

    return modules


def run():
    suite = unittest.TestSuite()

    for test in find():
        try:
            # If the module defines a suite() function, call it to get the suite.
            mod = __import__(test, globals(), locals(), ['suite'])
            suitefn = getattr(mod, 'suite')
            suite.addTest(suitefn)
        except (ImportError, AttributeError):
            # else, just load all the test cases from the module.
            suite.addTest(unittest.defaultTestLoader.loadTestsFromName(test))


    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__':
    run()
