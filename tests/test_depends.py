import os
import logging
import platform
import unittest
from copy import deepcopy
from pickle import dumps
from tempfile import TemporaryDirectory

from dhpython.depends import Dependencies

from .common import FakeOptions


def pep386(d):
    """Mark all pydist entries as being PEP386"""
    for k, v in d.items():
        if isinstance(v, str):
            d[k] = {'dependency': v}
            d[k].setdefault('standard', 'PEP386')
    return d


def prime_pydist(impl, pydist):
    """Fake the pydist data for impl. Returns a cleanup function"""
    from dhpython.pydist import load

    for name, entries in pydist.items():
        if not isinstance(entries, list):
            pydist[name] = entries = [entries]
        for i, entry in enumerate(entries):
            if isinstance(entry, str):
                entries[i] = entry = {'dependency': entry}
            entry.setdefault('name', name)
            entry.setdefault('standard', '')
            entry.setdefault('rules', [])
            entry.setdefault('versions', set())

    key = dumps(((impl,), {}))
    load.cache[key] = pydist
    return lambda: load.cache.pop(key)


class DependenciesTestCase(unittest.TestCase):
    pkg = 'foo'
    impl = 'cpython3'
    pydist = {}
    stats = {
        'compile': False,
        'dist-info': set(),
        'egg-info': set(),
        'ext_no_version': set(),
        'ext_vers': set(),
        'nsp.txt': set(),
        'private_dirs': {},
        'public_vers': set(),
        'requires.txt': set(),
        'shebangs': set(),
    }
    requires = {}
    dist_info_metadata = {}
    options = FakeOptions()
    parse = True

    def setUp(self):
        self.d = Dependencies(self.pkg, self.impl)

        stats = deepcopy(self.stats)
        write_files = {}
        if self.requires:
            for fn, lines in self.requires.items():
                write_files[fn] = lines
                stats['requires.txt'].add(fn)

        if self.dist_info_metadata:
            for fn, lines in self.dist_info_metadata.items():
                write_files[fn] = lines
                stats['dist-info'].add(fn)

        if write_files:
            self.tempdir = TemporaryDirectory()  # pylint: disable=consider-using-with
            self.addCleanup(self.tempdir.cleanup)
            old_wd = os.getcwd()
            os.chdir(self.tempdir.name)
            self.addCleanup(os.chdir, old_wd)

        for fn, lines in write_files.items():
            os.makedirs(os.path.dirname(fn))
            with open(fn, 'w', encoding="UTF-8") as f:
                f.write('\n'.join(lines))

        cleanup = prime_pydist(self.impl, self.pydist)
        self.addCleanup(cleanup)

        if self.parse:
            self.d.parse(stats, self.options)
        else:
            self.prepared_stats = stats

    def assertNotInDepends(self, pkg):
        """Assert that pkg doesn't appear *anywhere* in self.d.depends"""
        for dep in self.d.depends:
            for alt in dep.split('|'):
                alt = alt.strip().split('(', 1)[0].strip()
                if pkg == alt:
                    raise AssertionError(f'{pkg} appears in {alt}')


class TestRequiresCPython3(DependenciesTestCase):
    options = FakeOptions(guess_deps=True)
    pydist = {
        'bar': 'python3-bar',
        'baz': {'dependency': 'python3-baz', 'standard': 'PEP386'},
        'quux': {'dependency': 'python3-quux', 'standard': 'PEP440'},
    }
    requires = {
        'debian/foo/usr/lib/python3/dist-packages/foo.egg-info/requires.txt': (
            'bar',
            'baz >= 1.0',
            'quux >= 1.0a1',
        ),
    }

    def test_depends_on_bar(self):
        self.assertIn('python3-bar', self.d.depends)

    def test_depends_on_baz(self):
        self.assertIn('python3-baz (>= 1.0)', self.d.depends)

    def test_depends_on_quux(self):
        self.assertIn('python3-quux (>= 1.0~a1)', self.d.depends)


class TestRequiresCompatible(DependenciesTestCase):
    options = FakeOptions(guess_deps=True)
    pydist = {
        'bar': 'python3-bar',
        'baz': {'dependency': 'python3-baz', 'standard': 'PEP386'},
        'qux': {'dependency': 'python3-qux', 'standard': 'PEP386'},
        'quux': {'dependency': 'python3-quux', 'standard': 'PEP386'},
        'corge': {'dependency': 'python3-corge', 'standard': 'PEP440'},
    }
    requires = {
        'debian/foo/usr/lib/python3/dist-packages/foo.egg-info/requires.txt': (
            'bar',
            'baz ~= 1.1',
            'qux == 1.*',
            'quux',
            'corge == 1.0',
        ),
    }

    def test_depends_on_bar(self):
        self.assertIn('python3-bar', self.d.depends)

    def test_depends_on_baz(self):
        self.assertIn('python3-baz (>= 1.1), python3-baz (<< 2)', self.d.depends)

    def test_depends_on_qux(self):
        self.assertIn('python3-qux (>= 1.0), python3-qux (<< 2)', self.d.depends)

    def test_depends_on_corge(self):
        self.assertIn('python3-corge (>= 1.0), python3-corge (<< 1.1~)',
                      self.d.depends)


class TestRequiresDistPython3(DependenciesTestCase):
    options = FakeOptions(guess_deps=True)
    pydist = {
        'bar': 'python3-bar',
        'baz': {'dependency': 'python3-baz', 'standard': 'PEP386'},
        'qux': {'dependency': 'python3-qux', 'standard': 'PEP386'},
        'quux': {'dependency': 'python3-quux', 'standard': 'PEP386'},
        'corge': {'dependency': 'python3-corge', 'standard': 'PEP440'},
    }
    dist_info_metadata = {
        'debian/foo/usr/lib/python3/dist-packages/foo.dist-info/METADATA': (
            'Requires-Dist: bar',
            'Requires-Dist: baz >= 1.0',
            'Requires-Dist: qux == 1.*',
            'Requires-Dist: quux ~= 1.1',
            'Requires-Dist: corge == 1.0',
        ),
    }

    def test_depends_on_bar(self):
        self.assertIn('python3-bar', self.d.depends)

    def test_depends_on_baz(self):
        self.assertIn('python3-baz (>= 1.0)', self.d.depends)

    def test_depends_on_qux(self):
        self.assertIn('python3-qux (>= 1.0), python3-qux (<< 2)',
                      self.d.depends)

    def test_depends_on_quux(self):
        self.assertIn('python3-quux (>= 1.1), python3-quux (<< 2)',
                      self.d.depends)

    def test_depends_on_corge(self):
        self.assertIn('python3-corge (>= 1.0), python3-corge (<< 1.1~)',
                      self.d.depends)


class TestEnvironmentMarkersDistInfo(DependenciesTestCase):
    options = FakeOptions(guess_deps=True, depends_section=['feature'])
    pydist = pep386({
        'no_markers': 'python3-no-markers',
        'os_posix': 'python3-os-posix',
        'os_java': 'python3-os-java',
        'sys_platform_linux': 'python3-sys-platform-linux',
        'sys_platform_darwin': 'python3-sys-platform-darwin',
        'platform_machine_x86_64': 'python3-platform-machine-x86-64',
        'platform_machine_mips64': 'python3-platform-machine-mips64',
        'platform_python_implementation_cpython':
            'python3-platform-python-implementation-cpython',
        'platform_python_implementation_jython':
            'python3-platform-python-implementation-jython',
        'platform_release_lt2': 'python3-platform-release-lt2',
        'platform_release_ge2': 'python3-platform-release-ge2',
        'platform_system_linux': 'python3-platform-system-linux',
        'platform_system_windows': 'python3-platform-system-windows',
        'platform_version_lt1': 'python3-platform-version-lt1',
        'platform_version_ge1': 'python3-platform-version-ge1',
        'python_version_ge3': 'python3-python-version-ge3',
        'python_version_gt3': 'python3-python-version-gt3',
        'python_version_lt3': 'python3-python-version-lt3',
        'python_version_lt30': 'python3-python-version-lt30',
        'python_version_lt38': 'python3-python-version-lt38',
        'python_version_lt313': 'python3-python-version-lt313',
        'python_version_le313': 'python3-python-version-le313',
        'python_version_ge27': 'python3-python-version-ge27',
        'python_version_ge313': 'python3-python-version-ge313',
        'python_version_gt313': 'python3-python-version-gt313',
        'python_version_eq313': 'python3-python-version-eq313',
        'python_version_ne313': 'python3-python-version-ne313',
        'python_version_aeq313': 'python3-python-version-aeq313',
        'python_version_ceq313': 'python3-python-version-ceq313',
        'python_version_weq313': 'python3-python-version-weq313',
        'python_version_full_lt300': 'python3-python-version-full-lt300',
        'python_version_full_lt3131': 'python3-python-version-full-lt3131',
        'python_version_full_le3131': 'python3-python-version-full-le3131',
        'python_version_full_ge3131': 'python3-python-version-full-ge3131',
        'python_version_full_ge3131a1': 'python3-python-version-full-ge3131a1',
        'python_version_full_ge3131b1post1':
            'python3-python-version-full-ge3131b1post1',
        'python_version_full_gt3131': 'python3-python-version-full-gt3131',
        'python_version_full_eq3131': 'python3-python-version-full-eq3131',
        'python_version_full_ne3131': 'python3-python-version-full-ne3131',
        'python_version_full_aeq3131': 'python3-python-version-full-aeq3131',
        'python_version_full_ceq3131': 'python3-python-version-full-ceq3131',
        'python_version_full_weq313': 'python3-python-version-full-weq313',
        'implementation_name_cpython': 'python3-implementation-name-cpython',
        'implementation_name_pypy': 'python3-implementation-name-pypy',
        'implementation_version_lt313': 'python3-implementation-version-lt313',
        'implementation_version_ge313': 'python3-implementation-version-ge313',
        'invalid_marker': 'python3-invalid-marker',
        'extra_feature': 'python3-extra-feature',
        'extra_test': 'python3-extra-test',
        'complex_marker': 'python3-complex-marker',
        'complex_marker_2': 'python3-complex-marker-2',
        'no_markers_2': 'python3-no-markers-2',
    })
    dist_info_metadata = {
        'debian/foo/usr/lib/python3/dist-packages/foo.dist-info/METADATA': (
            "Requires-Dist: no_markers",
            "Requires-Dist: os_posix; (os_name == 'posix')",
            'Requires-Dist: os_java; os_name == "java"',
            "Requires-Dist: sys_platform_linux ; sys_platform == 'linux'",
            "Requires-Dist: sys_platform_darwin;sys_platform == 'darwin'",
            "Requires-Dist: platform_machine_x86_64; "
                "platform_machine == 'x86_64'",
            "Requires-Dist: platform_machine_mips64; "
                "platform_machine == 'mips64'",
            "Requires-Dist: platform_python_implementation_cpython; "
                "platform_python_implementation == 'CPython'",
            "Requires-Dist: platform_python_implementation_jython; "
                "platform_python_implementation == 'Jython'",
            "Requires-Dist: platform_release_lt2; platform_release < '2.0'",
            "Requires-Dist: platform_release_ge2; platform_release >= '2.0'",
            "Requires-Dist: platform_system_linux; platform_system == 'Linux'",
            "Requires-Dist: platform_system_windows; "
                "platform_system == 'Windows'",
            "Requires-Dist: platform_version_lt1; platform_version < '1'",
            "Requires-Dist: platform_version_ge1; platform_version >= '1'",
            "Requires-Dist: python_version_ge3; python_version >= '3'",
            "Requires-Dist: python_version_gt3; python_version > '3'",
            "Requires-Dist: python_version_lt3; python_version < '3'",
            "Requires-Dist: python_version_lt30; python_version < '3.0'",
            "Requires-Dist: python_version_lt38; python_version < '3.8'",
            "Requires-Dist: python_version_lt313; python_version < '3.13'",
            "Requires-Dist: python_version_le313; python_version <= '3.13'",
            "Requires-Dist: python_version_gt313; python_version > '3.13'",
            "Requires-Dist: python_version_ge27; python_version >= '2.7'",
            "Requires-Dist: python_version_ge313; python_version >= '3.13'",
            "Requires-Dist: python_version_eq313; python_version == '3.13'",
            "Requires-Dist: python_version_ne313; python_version != '3.13'",
            "Requires-Dist: python_version_aeq313; python_version === '3.13'",
            "Requires-Dist: python_version_ceq313; python_version ~= '3.13'",
            "Requires-Dist: python_version_weq313; python_version == '3.13.*'",
            "Requires-Dist: python_version_full_lt300; "
                "python_full_version < '3.0.0'",
            "Requires-Dist: python_version_full_lt3131; "
                "python_full_version < '3.13.1'",
            "Requires-Dist: python_version_full_le3131; "
                "python_full_version <= '3.13.1'",
            "Requires-Dist: python_version_full_gt3131; "
                "python_full_version > '3.13.1'",
            "Requires-Dist: python_version_full_ge3131; "
                "python_full_version >= '3.13.1'",
            "Requires-Dist: python_version_full_ge3131a1; "
                "python_full_version >= '3.13.1a1'",
            "Requires-Dist: python_version_full_ge3131b1post1; "
                "python_full_version >= '3.13.1b1.post1'",
            "Requires-Dist: python_version_full_eq3131; "
                "python_full_version == '3.13.1'",
            "Requires-Dist: python_version_full_ne3131; "
                "python_full_version != '3.13.1'",
            "Requires-Dist: python_version_full_aeq3131; "
                "python_full_version === '3.13.1'",
            "Requires-Dist: python_version_full_ceq3131; "
                "python_full_version ~= '3.13.1'",
            "Requires-Dist: python_version_full_weq313; "
                "python_full_version == '3.13.*'",
            "Requires-Dist: implementation_name_cpython; "
                "implementation_name == 'cpython'",
            "Requires-Dist: implementation_name_pypy; "
                "implementation_name == 'pypy'",
            "Requires-Dist: implementation_version_lt313; "
                "implementation_version < '3.13'",
            "Requires-Dist: implementation_version_ge313; "
                "implementation_version >= '3.13'",
            "Requires-Dist: invalid_marker; invalid_marker > '1'",
            "Requires-Dist: extra_feature; extra == 'feature'",
            "Requires-Dist: extra_test; extra == 'test'",
            "Requires-Dist: complex_marker; os_name != 'windows' "
                "and implementation_name == 'cpython'",
            "Requires-Dist: complex_marker_2; (python_version > \"3.4\") "
                "and extra == 'test'",
            "Requires-Dist: no_markers_2",
        ),
    }

    def test_depends_on_unmarked_packages(self):
        self.assertIn('python3-no-markers', self.d.depends)

    def test_depends_on_posix_packages(self):
        self.assertIn('python3-os-posix', self.d.depends)

    def test_skips_non_posix_packages(self):
        self.assertNotInDepends('python3-os-java')

    def test_depends_on_linux_packages(self):
        self.assertIn('python3-sys-platform-linux', self.d.depends)

    def test_skips_darwin_packages(self):
        self.assertNotInDepends('python3-sys-platform-darwin')

    def test_depends_on_x86_64_packages_on_x86_64(self):
        if platform.machine() == 'x86_64':
            self.assertIn('python3-platform-machine-x86-64', self.d.depends)
        else:
            self.assertNotInDepends('python3-platform-machine-x86-64')

    def test_depends_on_mips64_packages_on_mips64(self):
        if platform.machine() == 'mips64':
            self.assertIn('python3-platform-machine-mips64', self.d.depends)
        else:
            self.assertNotInDepends('python3-platform-machine-mips64')

    def test_depends_on_plat_cpython_packages(self):
        self.assertIn('python3-platform-python-implementation-cpython',
                      self.d.depends)

    def test_skips_plat_jython_packages(self):
        self.assertNotInDepends('python3-platform-python-implementation-jython')

    def test_skips_release_lt_2_packages(self):
        self.assertNotInDepends('python3-platform-release-lt2')

    def test_skips_release_gt_2_packages(self):
        self.assertNotInDepends('python3-platform-release-ge2')

    def test_depends_on_platform_linux_packages(self):
        self.assertIn('python3-platform-system-linux', self.d.depends)

    def test_skips_platform_windows_packages(self):
        self.assertNotInDepends('python3-platform-system-windows')

    def test_skips_platfrom_version_lt_1_packages(self):
        self.assertNotInDepends('python3-platform-version-lt1')

    def test_skips_platform_version_ge_1_packages(self):
        self.assertNotInDepends('python3-platform-version-ge1')

    def test_skips_py_version_lt_3_packages(self):
        self.assertNotInDepends('python3-python-version-lt3')

    def test_elides_py_version_ge_3(self):
        self.assertIn('python3-python-version-ge3', self.d.depends)

    def test_elides_py_version_gt_3(self):
        self.assertIn('python3-python-version-gt3', self.d.depends)

    def test_skips_py_version_lt_30_packages(self):
        self.assertNotInDepends('python3-python-version-lt30')

    def test_skips_py_version_lt_38_packages(self):
        self.assertNotInDepends('python3-python-version-lt38')

    def test_depends_on_py_version_lt_313_packages(self):
        self.assertIn('python3-python-version-lt313 '
                      '| python3-supported-min (>= 3.13)', self.d.depends)

    def test_depends_on_py_version_le_313_packages(self):
        self.assertIn('python3-python-version-le313 '
                      '| python3-supported-min (>> 3.13)', self.d.depends)

    def test_depends_on_py_version_ge_27_packages(self):
        self.assertIn('python3-python-version-ge27',
                      self.d.depends)

    def test_depends_on_py_version_ge_313_packages(self):
        self.assertIn('python3-python-version-ge313 '
                      '| python3-supported-max (<< 3.13)', self.d.depends)

    def test_depends_on_py_version_gt_313_packages(self):
        self.assertIn('python3-python-version-gt313 '
                      '| python3-supported-max (<= 3.13)', self.d.depends)

    def test_depends_on_py_version_eq_313_packages(self):
        self.assertIn(
            'python3-python-version-eq313 | python3-supported-max (<< 3.13) '
            '| python3-supported-min (>= 3.14)', self.d.depends)

    def test_depends_on_py_version_ne_313_packages(self):
        # Can't be represented in Debian depends
        self.assertIn('python3-python-version-ne313', self.d.depends)

    def test_depends_on_py_version_aeq_313_packages(self):
        self.assertIn(
            'python3-python-version-aeq313 | python3-supported-max (<< 3.13) '
            '| python3-supported-min (>> 3.13)', self.d.depends)

    def test_depends_on_py_version_ceq_313_packages(self):
        self.assertIn(
            'python3-python-version-ceq313 | python3-supported-max (<< 3.13) '
            '| python3-supported-min (>= 3.14)', self.d.depends)

    def test_depends_on_py_version_weq_313_packages(self):
        self.assertIn(
            'python3-python-version-weq313 | python3-supported-max (<< 3.13) '
            '| python3-supported-min (>= 3.14)', self.d.depends)

    def test_skips_py_version_full_lt_300_packages(self):
        self.assertNotInDepends('python3-python-version-full-lt300')

    def test_depends_on_py_version_full_lt_3131_packages(self):
        self.assertIn('python3-python-version-full-lt3131 '
                      '| python3-supported-min (>= 3.13.1)', self.d.depends)

    def test_depends_on_py_version_full_le_3131_packages(self):
        self.assertIn('python3-python-version-full-le3131 '
                      '| python3-supported-min (>> 3.13.1)', self.d.depends)

    def test_depends_on_py_version_full_ge_3131_packages(self):
        self.assertIn('python3-python-version-full-ge3131 '
                      '| python3-supported-max (<< 3.13.1)', self.d.depends)

    def test_depends_on_py_version_full_ge_3131a1_packages(self):
        # With full PEP-440 parsing this should be (<< 3.13.1~a1)
        self.assertIn('python3-python-version-full-ge3131a1 '
                      '| python3-supported-max (<< 3.13.0)', self.d.depends)

    def test_depends_on_py_version_full_ge_3131b1post1_packages(self):
        # With full PEP-440 parsing this should be (<< 3.13.1~b1.post1)
        self.assertIn('python3-python-version-full-ge3131a1 '
                      '| python3-supported-max (<< 3.13.0)', self.d.depends)

    def test_depends_on_py_version_full_gt_3131_packages(self):
        self.assertIn('python3-python-version-full-gt3131 '
                      '| python3-supported-max (<= 3.13.1)', self.d.depends)

    def test_depends_on_py_version_full_eq_3131_packages(self):
        self.assertIn('python3-python-version-full-eq3131 '
                      '| python3-supported-max (<< 3.13.1) '
                      '| python3-supported-min (>> 3.13.1)', self.d.depends)

    def test_depends_on_py_version_full_ne_3131_packages(self):
        # Can't be represented in Debian depends
        self.assertIn('python3-python-version-full-ne3131', self.d.depends)

    def test_skips_py_version_full_aeq_3131_packages(self):
        # Can't be represented in Debian depends
        self.assertNotInDepends('python3-python-version-full-aeq3131')

    def test_depends_on_py_version_full_ceq_3131_packages(self):
        self.assertIn('python3-python-version-full-ceq3131 '
                      '| python3-supported-max (<< 3.13.1) '
                      '| python3-supported-min (>= 3.14)', self.d.depends)

    def test_depends_on_py_version_full_weq_313_packages(self):
        self.assertIn('python3-python-version-full-weq313 '
                      '| python3-supported-max (<< 3.13) '
                      '| python3-supported-min (>= 3.14)', self.d.depends)

    def test_depends_on_sys_cpython_packages(self):
        self.assertIn('python3-implementation-name-cpython', self.d.depends)

    def test_depends_on_sys_pypy_packages(self):
        self.assertIn('python3-implementation-name-pypy', self.d.depends)

    def test_depends_on_sys_implementation_lt313_packages(self):
        self.assertIn('python3-implementation-version-lt313 '
                      '| python3-supported-min (>= 3.13)',
                      self.d.depends)

    def test_depends_on_sys_implementation_ge313_packages(self):
        self.assertIn('python3-implementation-version-ge313 '
                      '| python3-supported-max (<< 3.13)',
                      self.d.depends)

    def test_ignores_invalid_marker(self):
        self.assertNotInDepends('python3-invalid-marker')

    def test_depends_on_extra_feature_packages(self):
        self.assertIn('python3-extra-feature', self.d.depends)

    def test_skips_extra_test_packages(self):
        self.assertNotInDepends('python3-extra-test')

    def test_ignores_complex_environment_markers(self):
        self.assertNotInDepends('python3-complex-marker')
        self.assertNotInDepends('python3-complex-marker-2')

    def test_depends_on_un_marked_dependency_after_extra(self):
        self.assertIn('python3-no-markers-2', self.d.depends)


class TestEnvironmentMarkersEggInfo(TestEnvironmentMarkersDistInfo):
    dist_info_metadata = None
    requires = {
        'debian/foo/usr/lib/python3/dist-packages/foo.egg-info/requires.txt': (
            "no_markers",
            "[:(os_name == 'posix')]",
            "os_posix",
            '[:os_name == "java"]',
            "os_java",
            "[:sys_platform == 'linux']",
            "sys_platform_linux",
            "[:sys_platform == 'darwin']",
            "sys_platform_darwin",
            "[:platform_machine == 'x86_64']",
            "platform_machine_x86_64",
            "[:platform_machine == 'mips64']",
            "platform_machine_mips64",
            "[:platform_python_implementation == 'CPython']",
            "platform_python_implementation_cpython",
            "[:platform_python_implementation == 'Jython']",
            "platform_python_implementation_jython",
            "[:platform_release < '2.0']",
            "platform_release_lt2",
            "[:platform_release >= '2.0']",
            "platform_release_ge2",
            "[:platform_system == 'Linux']",
            "platform_system_linux",
            "[:platform_system == 'Windows']",
            "platform_system_windows",
            "[:platform_version < '1']",
            "platform_version_lt1",
            "[:platform_version >= '1']",
            "platform_version_ge1",
            "[:python_version >= '3']",
            "python_version_ge3",
            "[:python_version > '3']",
            "python_version_gt3",
            "[:python_version < '3']",
            "python_version_lt3",
            "[:python_version < '3.0']",
            "python_version_lt30",
            "[:python_version < '3.8']",
            "python_version_lt313",
            "[:python_version < '3.13']",
            "python_version_lt313",
            "[:python_version <= '3.13']",
            "python_version_le313",
            "[:python_version > '3.13']",
            "python_version_gt313",
            "[:python_version >= '2.7']",
            "python_version_ge27",
            "[:python_version >= '3.13']",
            "python_version_ge313",
            "[:python_version == '3.13']",
            "python_version_eq313",
            "[:python_version != '3.13']",
            "python_version_ne313",
            "[:python_version === '3.13']",
            "python_version_aeq313",
            "[:python_version ~= '3.13']",
            "python_version_ceq313",
            "[:python_version == '3.13.*']",
            "python_version_weq313",
            "[:python_full_version < '3.0.0']",
            "python_version_full_lt300",
            "[:python_full_version < '3.13.1']",
            "python_version_full_lt3131",
            "[:python_full_version <= '3.13.1']",
            "python_version_full_le3131",
            "[:python_full_version > '3.13.1']",
            "python_version_full_gt3131",
            "[:python_full_version >= '3.13.1']",
            "python_version_full_ge3131",
            "[:python_full_version >= '3.13.1a1']",
            "python_version_full_ge3131a1",
            "[:python_full_version >= '3.13.1b1.post1']",
            "python_version_full_ge3131b1post1",
            "[:python_full_version == '3.13.1']",
            "python_version_full_eq3131",
            "[:python_full_version != '3.13.1']",
            "python_version_full_ne3131",
            "[:python_full_version === '3.13.1']",
            "python_version_full_aeq3131",
            "[:python_full_version ~= '3.13.1']",
            "python_version_full_ceq3131",
            "[:python_full_version == '3.13.*']",
            "python_version_full_weq313",
            "[:implementation_name == 'cpython']",
            "implementation_name_cpython",
            "[:implementation_name == 'pypy']",
            "implementation_name_pypy",
            "[:implementation_version < '3.13']",
            "implementation_version_lt313",
            "[:implementation_version >= '3.13']",
            "implementation_version_ge313",
            "[:invalid_marker > '1']",
            "invalid_marker",
            "[feature]",
            "extra_feature",
            "[test]",
            "extra_test",
            "[:os_name != 'windows' and implementation_name == 'cpython']",
            "complex_marker",
            "[test:(os_name != 'windows')]",
            "complex_marker_2",
        ),
    }

    def test_depends_on_un_marked_dependency_after_extra(self):
        raise unittest.SkipTest('Not possible in requires.txt')


class TestIgnoresUnusedModulesDistInfo(DependenciesTestCase):
    options = FakeOptions(guess_deps=True, depends_section=['feature'])
    dist_info_metadata = {
        'debian/foo/usr/lib/python3/dist-packages/foo.dist-info/METADATA': (
            "Requires-Dist: unusued-complex-module ; "
                "(sys_platform == \"darwin\") and extra == 'nativelib'",
            "Requires-Dist: unused-win-module ; (sys_platform == \"win32\")",
            "Requires-Dist: unused-extra-module ; extra == 'unused'",
        ),
    }
    parse = False

    def test_ignores_unused_dependencies(self):
        if not hasattr(self, 'assertLogs'):
            raise unittest.SkipTest("Requires Python >= 3.4")
        with self.assertLogs(logger='dhpython', level=logging.INFO) as logs:
            self.d.parse(self.prepared_stats, self.options)
        for line in logs.output:
            self.assertTrue(
                line.startswith(
                    'INFO:dhpython:Ignoring complex environment marker'),
                'Expecting only complex environment marker messages, but '
                'got: {}'.format(line))


class TestIgnoresUnusedModulesEggInfo(DependenciesTestCase):
    options = FakeOptions(guess_deps=True, depends_section=['feature'])
    requires = {
        'debian/foo/usr/lib/python3/dist-packages/foo.egg-info/requires.txt': (
            "[nativelib:(sys_platform == 'darwin')]",
            "unusued-complex-module",
            "[:sys_platform == 'win32']",
            "unused-win-module",
            "[unused]",
            "unused-extra-module",
        )
    }
    parse = False

    def test_ignores_unused_dependencies(self):
        if not hasattr(self, 'assertNoLogs'):
            raise unittest.SkipTest("Requires Python >= 3.10")
        with self.assertNoLogs(logger='dhpython', level=logging.INFO):
            self.d.parse(self.prepared_stats, self.options)
