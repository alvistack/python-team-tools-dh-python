import os
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Sequence, cast
from unittest import TestCase

from dhpython.interpreter import Interpreter
from dhpython.fs import Scan, merge_WHEEL, share_files
from dhpython.version import Version

from .common import FakeOptions


class FSTestCase(TestCase):
    files: dict[str, Sequence[str]] = {}

    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.tempdir.cleanup)
        temp_path = Path(self.tempdir.name)
        for fn, contents in self.files.items():
            path = temp_path / fn
            setattr(self, path.name, path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('\n'.join(contents) + '\n')

    def assertFileContents(self, path: Path, contents: str | Sequence[str]) -> None:
        """Assert that the contents of path is contents

        Contents may be specified as a list of strings, one per line, without
        line-breaks.
        """
        if isinstance(contents, (list, tuple)):
            contents = '\n'.join(contents) + '\n'
        assert isinstance(contents, str)
        with path.open('r') as f:
            self.assertMultiLineEqual(contents, f.read())


class MergeTagsTest(FSTestCase):
    a: Path
    b: Path
    files = {
        'a': ('foo', 'Tag: A'),
        'b': ('foo', 'Tag: B'),
    }

    def test_merge_wheel(self) -> None:
        merge_WHEEL(self.a, self.b)
        self.assertFileContents(self.b, ('foo', 'Tag: B', 'Tag: A'))


class ShareFilesTestCase(FSTestCase):
    impl = 'cpython3'
    options: dict[str, Any] = {}

    def setUp(self) -> None:
        super().setUp()
        self.destdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.destdir.cleanup)
        self.interpreter = Interpreter(self.impl)

    def share_files(self, options: dict[str, Any] | None = None) -> None:
        if options is None:
            options = self.options
        share_files(self.tempdir.name, self.destdir.name, self.interpreter,
                    cast(Namespace, FakeOptions(**options)))

    def destPath(self, name: str) -> Path:
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

    def test_removes_license_files(self) -> None:
        self.share_files()
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

    def test_removes_license_files(self) -> None:
        self.share_files()
        self.assertFalse(self.destPath('foo.dist-info/COPYING.LESSER').exists())
        self.assertFalse(self.destPath('foo.dist-info/COPYING').exists())


class CExtensionsRenameTest(ShareFilesTestCase):
    def setUp(self) -> None:
        ver = Interpreter(self.impl).default_version
        self.files = {
            f'usr/lib/python{ver}/foo.so': ('binary-data'),
        }
        self.ext_filename = f'usr/lib/python{ver}/foo.so'
        super().setUp()

    def test_python_extensions(self) -> None:
        self.share_files()
        self.assertFalse(self.destPath(self.ext_filename).exists())
        expected_name = self.interpreter.check_extname(self.ext_filename)
        self.assertTrue(expected_name)
        assert expected_name
        self.assertTrue(self.destPath(expected_name).exists())

    def test_no_ext_rename(self) -> None:
        self.share_files(options={"no_ext_rename": True})
        self.assertTrue(self.destPath(self.ext_filename).exists())


class ScanTestCase(FSTestCase):
    impl = 'cpython3'
    options: dict[str, Any] = {}
    package = "python3-test"

    def setUp(self) -> None:
        super().setUp()
        pwd = os.getcwd()
        try:
            os.chdir(self.tempdir.name)
            self.scan = Scan(
                interpreter=Interpreter(self.impl),
                package=self.package,
                options=cast(Namespace, FakeOptions(**self.options)),
            )
        finally:
            os.chdir(pwd)


class UnversionedExtensionScanTest(ScanTestCase):
    files = {
        'debian/python3-test/usr/lib/python3/dist-packages/foo.so': "contents",
    }
    options = {
        "no_ext_rename": True,
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result['public_vers'], {Version('3')})
        self.assertEqual(self.scan.result['ext_vers'], set())
        self.assertEqual(
            self.scan.result['ext_no_version'],
            {'debian/python3-test/usr/lib/python3/dist-packages/foo.so'},
        )
        self.assertEqual(self.scan.result['ext_stableabi'], set())


class UnversionedExtensionRenamedScanTest(ScanTestCase):
    files = {
        'debian/python3-test/usr/lib/python3/dist-packages/foo.so': "contents",
    }

    def test_scan(self) -> None:
        version = Interpreter(self.impl).default_version
        self.assertEqual(self.scan.result['public_vers'], {Version('3')})
        self.assertEqual(self.scan.result['ext_vers'], {version})
        self.assertEqual(self.scan.result['ext_no_version'], set())
        self.assertEqual(self.scan.result['ext_stableabi'], set())


class StableABIExtensionDependenciesTest(ScanTestCase):
    files = {
        (
            'debian/python3-test/usr/lib/python3/dist-packages/'
            'foo.abi3-x86_64-linux-gnu.so'
        ): "contents",
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result['public_vers'], {Version('3')})
        self.assertEqual(self.scan.result['ext_vers'], set())
        self.assertEqual(self.scan.result['ext_no_version'], set())
        self.assertEqual(
            self.scan.result['ext_stableabi'],
            {
                'debian/python3-test/usr/lib/python3/dist-packages/'
                'foo.abi3-x86_64-linux-gnu.so'
            },
        )


class VersionedExtensionDependenciesTest(ScanTestCase):
    files = {
        (
            'debian/python3-test/usr/lib/python3/dist-packages/'
            'foo.cpython-314-x86_64-linux-gnu.so'
        ): "contents",
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result['public_vers'], {Version('3')})
        self.assertEqual(self.scan.result['ext_vers'], {Version('3.14')})
        self.assertEqual(self.scan.result['ext_no_version'], set())
        self.assertEqual(self.scan.result['ext_stableabi'], set())
