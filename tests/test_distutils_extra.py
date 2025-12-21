import os
import unittest
from argparse import Namespace
from copy import deepcopy
from tempfile import TemporaryDirectory
from typing import cast

from dhpython.depends import Dependencies
from dhpython.fs import ScanResult
from dhpython.pydist import Standard

from .common import FakeOptions
from .test_depends import prime_pydist, pydist


class TestDistutilsExtra(unittest.TestCase):
    options = FakeOptions(guess_deps=True)
    pydist = {
        "bar": [pydist(name="bar", dependency="python3-bar")],
        "baz": [pydist(name="baz", dependency="python3-baz", standard=Standard.PEP386)],
        "quux": [
            pydist(name="quux", dependency="python3-quux", standard=Standard.PEP386)
        ],
    }
    pkg = "foo"
    impl = "cpython3"
    stats = ScanResult(
        {
            "compile": False,
            "dist-info": set(),
            "egg-info": set(("PKG-INFO",)),
            "ext_no_version": set(),
            "ext_stableabi": set(),
            "ext_vers": set(),
            "nsp.txt": set(),
            "private_dirs": {},
            "public_vers": set(),
            "requires.txt": set(),
            "shebangs": set(),
        }
    )

    def test_depends_on_bar(self) -> None:
        self.d = Dependencies(self.pkg, self.impl)
        stats = deepcopy(self.stats)
        self.tempdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.tempdir.cleanup)
        old_wd = os.getcwd()
        os.chdir(self.tempdir.name)
        self.addCleanup(os.chdir, old_wd)
        with open(self.tempdir.name + "/PKG-INFO", "w", encoding="UTF-8") as f:
            f.write(
                """Metadata-Version: 2.1
Name: gTranscribe
Version: 0.11
Summary: gTranscribe
Home-page: https://github.com/innir/gtranscribe
Author: Philip Rinn
Author-email: rinni@inventati.org
License: GPL-3
Requires: bar

gTranscribe is a software focused on easy transcription of spoken words.
"""
            )
        cleanup = prime_pydist(self.impl, self.pydist)
        self.addCleanup(cleanup)
        self.d.parse(stats, cast(Namespace, self.options))
        self.assertIn("python3-bar", self.d.depends)
