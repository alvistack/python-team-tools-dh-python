import os
import unittest
from copy import deepcopy
from tempfile import TemporaryDirectory

from dhpython.depends import Dependencies

from test_depends import FakeOptions, prime_pydist


class TestDistutilsExtra(unittest.TestCase):
    options = FakeOptions(guess_deps=True)
    pydist = {
        'bar': 'python3-bar',
        'baz': {'dependency': 'python3-baz', 'standard': 'PEP386'},
        'quux': {'dependency': 'python3-quux', 'standard': 'PEP386'},
    }
    pkg = 'foo'
    impl = 'cpython3'
    stats = {
        'compile': False,
        'dist-info': set(),
        'egg-info': set(('PKG-INFO',)),
        'ext_no_version': set(),
        'ext_vers': set(),
        'nsp.txt': set(),
        'private_dirs': {},
        'public_vers': set(),
        'requires.txt': set(),
        'shebangs': set(),
    }
    requires = {}

    def test_depends_on_bar(self):
        self.d = Dependencies(self.pkg, self.impl)
        stats = deepcopy(self.stats)
        self.tempdir = TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        old_wd = os.getcwd()
        os.chdir(self.tempdir.name)
        self.addCleanup(os.chdir, old_wd)
        with open(self.tempdir.name + '/PKG-INFO', 'w') as f:
            f.write("""Metadata-Version: 2.1
Name: gTranscribe
Version: 0.11
Summary: gTranscribe
Home-page: https://github.com/innir/gtranscribe
Author: Philip Rinn
Author-email: rinni@inventati.org
License: GPL-3
Requires: bar

gTranscribe is a software focused on easy transcription of spoken words.
""")
        cleanup = prime_pydist(self.impl, self.pydist)
        self.addCleanup(cleanup)
        self.d.parse(stats, self.options)
        self.assertIn('python3-bar', self.d.depends)
