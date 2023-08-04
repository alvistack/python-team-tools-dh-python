from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase

from dhpython.interpreter import Interpreter
from dhpython.fs import merge_WHEEL, share_files

from tests.common import FakeOptions


class MergeWheelTestCase(TestCase):
    files = {}
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        temp_path = Path(self.tempdir.name)
        for fn, contents in self.files.items():
            path = temp_path / fn
            setattr(self, path.name, path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w') as f:
                f.write('\n'.join(contents))
                f.write('\n')

    def assertFileContents(self, path, contents):
        """Assert that the contents of path is contents

        Contents may be specified as a list of strings, one per line, without
        line-breaks.
        """
        if isinstance(contents, (list, tuple)):
            contents = '\n'.join(contents) + '\n'
        with path.open('r') as f:
            self.assertMultiLineEqual(contents, f.read())


class MergeTagsTest(MergeWheelTestCase):
    files = {
        'a': ('foo', 'Tag: A'),
        'b': ('foo', 'Tag: B'),
    }

    def test_merge_wheel(self):
        merge_WHEEL(self.a, self.b)
        self.assertFileContents(self.b, ('foo', 'Tag: B', 'Tag: A'))


class ShareFilesTestCase(MergeWheelTestCase):
    impl = 'cpython3'
    options = {}

    def setUp(self):
        super().setUp()
        self.destdir = TemporaryDirectory()
        self.addCleanup(self.destdir.cleanup)
        share_files(self.tempdir.name, self.destdir.name,
                    Interpreter(self.impl),
                    FakeOptions(**self.options))

    def destPath(self, name):
        return Path(self.destdir.name) / name


class HatchlingLicenseTest(ShareFilesTestCase):
    files = {
        'foo.dist-info/license_files/LICENSE.txt': ('foo'),
        'foo.dist-info/licenses/COPYING': ('foo'),
        'foo.dist-info/RECORD': (
            'foo.dist-info/license_files/LICENSE.txt,sha256=2c26b46b68ffc68ff99'
            'b453c1d30413413422d706483bfa0f98a5e886266e7ae,4',
            'foo.dist-info/licenses/COPYING,sha256=2c26b46b68ffc68ff99b453c1d30'
            '413413422d706483bfa0f98a5e886266e7ae,4',
            'foo.dist-info/WHEEL,sha256=447fb61fa39a067229e1cce8fc0953bfced53ea'
            'c85d1844f5940f51c1fcba725,6'),
        'foo.dist-info/WHEEL': ('foo'),
    }

    def test_removes_license_files(self):
        self.assertFalse(
            self.destPath('foo.dist-info/license_files/LICENSE.txt').exists())
        self.assertFalse(
            self.destPath('foo.dist-info/licenses/COPYING').exists())


class FlitLicenseTest(ShareFilesTestCase):
    files = {
        'foo.dist-info/COPYING': ('foo'),
        'foo.dist-info/COPYING.LESSER': ('foo'),
        'foo.dist-info/RECORD': (
            'foo.dist-info/COPYING,sha256=2c26b46b68ffc68ff99b453c1d30413413422'
            'd706483bfa0f98a5e886266e7ae,4',
            'foo.dist-info/COPYING.LESSER,sha256=2c26b46b68ffc68ff99b453c1d3041'
            '3413422d706483bfa0f98a5e886266e7ae,4',
            'foo.dist-info/WHEEL,sha256=447fb61fa39a067229e1cce8fc0953bfced53ea'
            'c85d1844f5940f51c1fcba725,6'),
        'foo.dist-info/WHEEL': ('foo'),
    }

    def test_removes_license_files(self):
        self.assertFalse(self.destPath('foo.dist-info/COPYING.LESSER').exists())
        self.assertFalse(self.destPath('foo.dist-info/COPYING').exists())
