#!/usr/bin/env python3
"""DIMACS command-line solver for the tests of the dimacs:<binary> backend: runs minicdcl on the given file and prints
SAT-competition output. (Any real solver with that output format is used the same way.)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import minicdcl
sys.exit(minicdcl.main(sys.argv[-1:]))
