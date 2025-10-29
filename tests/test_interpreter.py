import sys
import unittest
from os import environ
from os.path import exists
from dhpython.interpreter import Interpreter


class TestInterpreter(unittest.TestCase):
    def setUp(self):
        self._triplet = environ.get('DEB_HOST_MULTIARCH')
        environ['DEB_HOST_MULTIARCH'] = 'MYARCH'

    def tearDown(self):
        if self._triplet:
            environ['DEB_HOST_MULTIARCH'] = self._triplet
        else:
            del environ['DEB_HOST_MULTIARCH']

    @unittest.skipUnless(exists('/usr/bin/python3.11'), 'python3.11 is not installed')
    def test_python311(self):
        i = Interpreter('python3.11')
        self.assertEqual(i.soabi(), 'cpython-311')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-311-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-32m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-311-OTHER.so'))  # different architecture
        self.assertEqual(i.check_extname('foo.cpython-311.so'), r'foo.cpython-311-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-311-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.11-dbg'), 'python3.11-dbg is not installed')
    def test_python311dbg(self):
        i = Interpreter('python3.11-dbg')
        self.assertEqual(i.soabi(), 'cpython-311d')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-311d-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-32m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-311-OTHER.so'))  # different architecture
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-311d-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.12'), 'python3.12 is not installed')
    def test_python312(self):
        i = Interpreter('python3.12')
        self.assertEqual(i.soabi(), 'cpython-312')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-312-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-32m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-312-OTHER.so'))  # different architecture
        self.assertEqual(i.check_extname('foo.cpython-312.so'), r'foo.cpython-312-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-312-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.12-dbg'), 'python3.12-dbg is not installed')
    def test_python312dbg(self):
        i = Interpreter('python3.12-dbg')
        self.assertEqual(i.soabi(), 'cpython-312d')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-312d-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-32m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-312-OTHER.so'))  # different architecture
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-312d-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.13'), 'python3.13 is not installed')
    def test_python313(self):
        i = Interpreter('python3.13')
        self.assertEqual(i.soabi(), 'cpython-313')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-313-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-33m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-313-OTHER.so'))  # different architecture
        self.assertEqual(i.check_extname('foo.cpython-313.so'), r'foo.cpython-313-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-313-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.13-dbg'), 'python3.13-dbg is not installed')
    def test_python313dbg(self):
        i = Interpreter('python3.13-dbg')
        self.assertEqual(i.soabi(), 'cpython-313d')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-313d-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-33m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-313-OTHER.so'))  # different architecture
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-313d-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.14'), 'python3.14 is not installed')
    def test_python314(self):
        i = Interpreter('python3.14')
        self.assertEqual(i.soabi(), 'cpython-314')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-314-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-34m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-314-OTHER.so'))  # different architecture
        self.assertEqual(i.check_extname('foo.cpython-314.so'), r'foo.cpython-314-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-314-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3.14-dbg'), 'python3.14-dbg is not installed')
    def test_python314dbg(self):
        i = Interpreter('python3.14-dbg')
        self.assertEqual(i.soabi(), 'cpython-314d')
        self.assertEqual(i.check_extname('foo.so'), r'foo.cpython-314d-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-34m.so'))  # different version
        self.assertIsNone(i.check_extname('foo.cpython-314-OTHER.so'))  # different architecture
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), r'foo/bar/baz.cpython-314d-MYARCH.so')

    def test_python3(self):
        i = Interpreter('python{}.{}'.format(*sys.version_info[:2]))
        pyver = '{}{}'.format(*sys.version_info[:2])
        self.assertEqual(i.soabi(), 'cpython-' + pyver)
        self.assertEqual(i.check_extname('foo.so'), rf'foo.cpython-{pyver}-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-32m.so'))  # different version
        self.assertIsNone(i.check_extname(f'foo.cpython-{pyver}-OTHER.so'))  # different architecture
        self.assertEqual(i.check_extname(f'foo.cpython-{pyver}.so'), rf'foo.cpython-{pyver}-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), rf'foo/bar/baz.cpython-{pyver}-MYARCH.so')

    @unittest.skipUnless(exists('/usr/bin/python3-dbg'), 'python3-dbg is not installed')
    def test_python3dbg(self):
        i = Interpreter('python{}.{}-dbg'.format(*sys.version_info[:2]))
        pyver = '{}{}'.format(*sys.version_info[:2])
        self.assertEqual(i.soabi(), f'cpython-{pyver}d')
        self.assertEqual(i.check_extname('foo.so'), rf'foo.cpython-{pyver}d-MYARCH.so')
        self.assertIsNone(i.check_extname('foo.cpython-32m.so'))  # different version
        self.assertIsNone(i.check_extname(f'foo.cpython-{pyver}-OTHER.so'))  # different architecture
        self.assertIsNone(i.check_extname('foo.abi3.so'))
        self.assertEqual(i.check_extname('foo/bar/bazmodule.so'), rf'foo/bar/baz.cpython-{pyver}d-MYARCH.so')

    def test_bare_module(self):
        i = Interpreter('python{}.{}'.format(*sys.version_info[:2]))
        pyver = '{}{}'.format(*sys.version_info[:2])
        self.assertEqual(i.check_extname('module.so'), rf'module.cpython-{pyver}-MYARCH.so')
        self.assertEqual(i.check_extname('_module.so'), rf'_module.cpython-{pyver}-MYARCH.so')


if __name__ == '__main__':
    unittest.main()
