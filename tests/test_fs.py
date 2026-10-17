import os
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase

from dhpython.interpreter import Interpreter
from dhpython.fs import Scan, share_files
from dhpython.options import DHPythonOptions
from dhpython.version import Version


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
            path.write_text("\n".join(contents) + "\n")

    def assertFileContents(self, path: Path, contents: str | Sequence[str]) -> None:
        """Assert that the contents of path is contents

        Contents may be specified as a list of strings, one per line, without
        line-breaks.
        """
        if isinstance(contents, (list, tuple)):
            contents = "\n".join(contents) + "\n"
        assert isinstance(contents, str)
        with path.open("r") as f:
            self.assertMultiLineEqual(contents, f.read())


class ShareFilesTestCase(FSTestCase):
    impl = "cpython3"
    options: dict[str, Any] = {}

    def setUp(self) -> None:
        super().setUp()
        self.destdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.destdir.cleanup)
        self.interpreter = Interpreter(self.impl)

    def share_files(
        self,
        srcdir: str | None = None,
        interpreter: Interpreter | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        if srcdir is None:
            srcdir = self.tempdir.name
        if interpreter is None:
            interpreter = self.interpreter
        if options is None:
            options = self.options
        share_files(
            srcdir,
            self.destdir.name,
            interpreter,
            DHPythonOptions(**options),
        )

    def destPath(self, name: str) -> Path:
        return Path(self.destdir.name) / name


class HatchlingLicenseTest(ShareFilesTestCase):
    files = {
        "foo.dist-info/license_files/LICENSE.txt": ("foo"),
        "foo.dist-info/licenses/COPYING": ("foo"),
        "foo.dist-info/RECORD": (
            "foo.dist-info/license_files/LICENSE.txt,sha256=2c26b46b68ffc68ff99"
            "b453c1d30413413422d706483bfa0f98a5e886266e7ae,4",
            "foo.dist-info/licenses/COPYING,sha256=2c26b46b68ffc68ff99b453c1d30"
            "413413422d706483bfa0f98a5e886266e7ae,4",
            "foo.dist-info/WHEEL,sha256=447fb61fa39a067229e1cce8fc0953bfced53ea"
            "c85d1844f5940f51c1fcba725,6",
        ),
        "foo.dist-info/WHEEL": ("foo"),
    }

    def test_removes_license_files(self) -> None:
        self.share_files()
        self.assertFalse(
            self.destPath("foo.dist-info/license_files/LICENSE.txt").exists()
        )
        self.assertFalse(self.destPath("foo.dist-info/licenses/COPYING").exists())


class FlitLicenseTest(ShareFilesTestCase):
    files = {
        "foo.dist-info/COPYING": ("foo"),
        "foo.dist-info/COPYING.LESSER": ("foo"),
        "foo.dist-info/RECORD": (
            "foo.dist-info/COPYING,sha256=2c26b46b68ffc68ff99b453c1d30413413422"
            "d706483bfa0f98a5e886266e7ae,4",
            "foo.dist-info/COPYING.LESSER,sha256=2c26b46b68ffc68ff99b453c1d3041"
            "3413422d706483bfa0f98a5e886266e7ae,4",
            "foo.dist-info/WHEEL,sha256=447fb61fa39a067229e1cce8fc0953bfced53ea"
            "c85d1844f5940f51c1fcba725,6",
        ),
        "foo.dist-info/WHEEL": ("foo"),
    }

    def test_removes_license_files(self) -> None:
        self.share_files()
        self.assertFalse(self.destPath("foo.dist-info/COPYING.LESSER").exists())
        self.assertFalse(self.destPath("foo.dist-info/COPYING").exists())


class CExtensionsRenameTest(ShareFilesTestCase):
    def setUp(self) -> None:
        ver = Interpreter(self.impl).default_version
        self.files = {
            f"usr/lib/python{ver}/foo.so": ("binary-data"),
        }
        self.ext_filename = f"usr/lib/python{ver}/foo.so"
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


class EntryPointsMergeTest(ShareFilesTestCase):
    files = {
        "default/foo.dist-info/entry_points.txt": ("default",),
        "next/foo.dist-info/entry_points.txt": ("non-default",),
    }

    def test_merge(self) -> None:
        self.share_files(srcdir=f"{self.tempdir.name}/default")
        self.share_files(srcdir=f"{self.tempdir.name}/next")
        expected_path = "foo.dist-info/entry_points.txt"
        self.assertTrue(self.destPath(expected_path).exists())
        self.assertEqual(self.destPath(expected_path).read_text(), "default\n")


class FailedMergeTest(ShareFilesTestCase):
    files = {
        "default/foo.py": ("default",),
        "next/foo.py": ("next",),
    }

    def test_merge(self) -> None:
        self.share_files(srcdir=f"{self.tempdir.name}/default")
        with self.assertRaises(SystemExit), self.assertLogs("dhpython") as cm:
            self.share_files(srcdir=f"{self.tempdir.name}/next")
        self.assertEqual(
            cm.output,
            [
                (
                    f"WARNING:dhpython:Paths differ: "
                    f"{self.tempdir.name}/next/foo.py and "
                    f"{self.destdir.name}/foo.py"
                ),
                (
                    f"ERROR:dhpython:Not everything in "
                    f"'{self.tempdir.name}/next' was able to be "
                    f"merged into '{self.destdir.name}'."
                ),
                f"INFO:dhpython:Remaining files: {self.tempdir.name}/next/foo.py",
            ],
        )

    def test_override(self) -> None:
        self.share_files(srcdir=f"{self.tempdir.name}/default")
        self.share_files(
            srcdir=f"{self.tempdir.name}/next",
            options={"allow_unmerged_dist_packages": True},
        )


class ScanTestCase(FSTestCase):
    impl = "cpython3"
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
                options=DHPythonOptions(**self.options),
            )
        finally:
            os.chdir(pwd)


class UnversionedExtensionScanTest(ScanTestCase):
    files = {
        "debian/python3-test/usr/lib/python3/dist-packages/foo.so": "contents",
    }
    options = {
        "no_ext_rename": True,
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result["public_vers"], {Version("3")})
        self.assertEqual(self.scan.result["ext_vers"], set())
        self.assertEqual(
            self.scan.result["ext_no_version"],
            {"debian/python3-test/usr/lib/python3/dist-packages/foo.so"},
        )
        self.assertEqual(self.scan.result["ext_stableabi"], set())


class UnversionedExtensionRenamedScanTest(ScanTestCase):
    files = {
        "debian/python3-test/usr/lib/python3/dist-packages/foo.so": "contents",
    }

    def test_scan(self) -> None:
        version = Interpreter(self.impl).default_version
        self.assertEqual(self.scan.result["public_vers"], {Version("3")})
        self.assertEqual(self.scan.result["ext_vers"], {version})
        self.assertEqual(self.scan.result["ext_no_version"], set())
        self.assertEqual(self.scan.result["ext_stableabi"], set())


class StableABIExtensionDependenciesTest(ScanTestCase):
    files = {
        (
            "debian/python3-test/usr/lib/python3/dist-packages/"
            "foo.abi3-x86_64-linux-gnu.so"
        ): "contents",
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result["public_vers"], {Version("3")})
        self.assertEqual(self.scan.result["ext_vers"], set())
        self.assertEqual(self.scan.result["ext_no_version"], set())
        self.assertEqual(
            self.scan.result["ext_stableabi"],
            {
                "debian/python3-test/usr/lib/python3/dist-packages/"
                "foo.abi3-x86_64-linux-gnu.so"
            },
        )


class VersionedExtensionDependenciesTest(ScanTestCase):
    files = {
        (
            "debian/python3-test/usr/lib/python3/dist-packages/"
            "foo.cpython-314-x86_64-linux-gnu.so"
        ): "contents",
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result["public_vers"], {Version("3")})
        self.assertEqual(self.scan.result["ext_vers"], {Version("3.14")})
        self.assertEqual(self.scan.result["ext_no_version"], set())
        self.assertEqual(self.scan.result["ext_stableabi"], set())


class VersionedExtension315DependenciesTest(ScanTestCase):
    files = {
        (
            "debian/python3-test/usr/lib/python3/dist-packages/"
            "foo.cpython-315-x86_64-linux-gnu.so"
        ): "contents",
    }

    def test_scan(self) -> None:
        self.assertEqual(self.scan.result["public_vers"], {Version("3")})
        self.assertEqual(self.scan.result["ext_vers"], {Version("3.15")})
        self.assertEqual(self.scan.result["ext_no_version"], set())
        self.assertEqual(self.scan.result["ext_stableabi"], set())


class CommonModuleNameTests(FSTestCase):
    impl = "cpython3"
    options: dict[str, Any] = {}
    package = "python3-test"
    files = {
        "debian/python3-test/usr/lib/python3/dist-packages/build/__init__.py": "",
    }

    def scan(self) -> None:
        pwd = os.getcwd()
        try:
            os.chdir(self.tempdir.name)
            Scan(
                interpreter=Interpreter(self.impl),
                package=self.package,
                options=DHPythonOptions(**self.options),
            )
        finally:
            os.chdir(pwd)

    def test_error(self) -> None:
        with (
            self.assertRaises(SystemExit),
            self.assertLogs("dhpython") as cm,
        ):
            self.scan()
        self.assertEqual(
            cm.output,
            [
                "ERROR:dhpython:python3-test includes a common build directory "
                "name 'build' as a module. Likely due to a mis-configured "
                "build system installing things it shouldn't."
            ],
        )

    def test_matching_package_name(self) -> None:
        self.package = "python3-build"
        self.scan()

    def test_explicit_override(self) -> None:
        self.options = {
            "allow_build_directory_module_name": True,
        }
        self.scan()
