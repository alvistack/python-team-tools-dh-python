from pathlib import Path
from tempfile import TemporaryDirectory, NamedTemporaryFile
import os
import unittest

from dhpython.tools import fix_shebang, relpath, move_matching_files


class TestRelpath(unittest.TestCase):
    def test_common_parent_dir(self):
        r = relpath('/usr/share/python-foo/foo.py', '/usr/bin/foo')
        self.assertEqual(r, '../share/python-foo/foo.py')

    def test_strips_common_prefix(self):
        r = relpath('/usr/share/python-foo/foo.py', '/usr/share')
        self.assertEqual(r, 'python-foo/foo.py')

    def test_trailing_slash_ignored(self):
        r = relpath('/usr/share/python-foo/foo.py', '/usr/share/')
        self.assertEqual(r, 'python-foo/foo.py')


class TestMoveMatchingFiles(unittest.TestCase):
    def setUp(self):
        self.tmpdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.tmpdir.cleanup)
        os.makedirs(self.tmppath('foo/bar/a/b/c/spam'))
        for path in ('foo/bar/a/b/c/spam/file.so',
                     'foo/bar/a/b/c/spam/file.py'):
            with open(self.tmppath(path), 'wb'):
                # create a 0 byte file for the test
                pass

        move_matching_files(self.tmppath('foo/bar/'),
                            self.tmppath('foo/baz/'),
                            r'spam/.*\.so$')

    def tmppath(self, *path):
        return os.path.join(self.tmpdir.name, *path)

    def test_moved_matching_file(self):
        self.assertTrue(os.path.exists(
            self.tmppath('foo/baz/a/b/c/spam/file.so')))

    def test_left_non_matching_file(self):
        self.assertTrue(os.path.exists(
            self.tmppath('foo/bar/a/b/c/spam/file.py')))


class TestFixShebang(unittest.TestCase):
    def setUp(self):
        self.tmpfile = Path(NamedTemporaryFile(
            prefix="dhptest_", suffix="_shebang.py", delete=False).name)
        self.addCleanup(self.tmpfile.unlink)

    def write_shebang(self, shebang):
        self.tmpfile.write_text(shebang + "\nprint('This is Python')\n")

    def assert_shebang(self, shebang):
        contents = self.tmpfile.read_text().splitlines()
        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0], shebang)
        self.assertEqual(contents[1], "print('This is Python')")

    def test_perl(self):
        self.write_shebang("#!/usr/bin/perl")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#!/usr/bin/perl")

    def test_unversioned(self):
        self.write_shebang("#!/usr/bin/python")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#! /usr/bin/python3")

    def test_python2(self):
        self.write_shebang("#!/usr/bin/python2")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#!/usr/bin/python2")

    def test_python2_7(self):
        self.write_shebang("#!/usr/bin/python2.7")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#!/usr/bin/python2.7")

    def test_python3(self):
        self.write_shebang("#!/usr/bin/python3")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#! /usr/bin/python3")

    def test_python3_13(self):
        self.write_shebang("#!/usr/bin/python3.13")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#!/usr/bin/python3.13")

    def test_env_unversioned(self):
        self.write_shebang("#!/usr/bin/env python")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#! /usr/bin/python3")

    def test_env_python3(self):
        self.write_shebang("#!/usr/bin/env python3")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#! /usr/bin/python3")

    def test_env_python3_13(self):
        self.write_shebang("#!/usr/bin/env python3.13")
        fix_shebang(self.tmpfile)
        self.assert_shebang("#! /usr/bin/python3.13")

    def test_replacement(self):
        self.write_shebang("#!/usr/bin/env python")
        fix_shebang(self.tmpfile, "/usr/bin/foo")
        self.assert_shebang("#! /usr/bin/foo")
