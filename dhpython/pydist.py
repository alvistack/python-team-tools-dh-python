# Copyright © 2010-2020 Piotr Ożarowski <piotr@debian.org>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import email
import logging
import platform
import os
import re
import subprocess
from argparse import Namespace
from enum import Enum, StrEnum, auto
from functools import cache, partial
from os.path import exists, isdir, join
from typing import Literal, NamedTuple, TypedDict, cast

if __name__ == '__main__':
    import sys
    sys.path.append(os.path.abspath(join(os.path.dirname(__file__), '..')))

from dhpython import PKG_PREFIX_MAP, PUBLIC_DIR_RE,\
    PYDIST_DIRS, PYDIST_OVERRIDES_FNAMES, PYDIST_DPKG_SEARCH_TPLS
from dhpython.debhelper import BD
from dhpython.markers import ComplexEnvironmentMarker, parse_environment_marker
from dhpython.version import get_requested_versions, Version

log = logging.getLogger('dhpython')

PYDIST_RE = re.compile(r"""
    (?P<name>[A-Za-z][A-Za-z0-9_.-]*)            # Python distribution name
    \s*
    (?P<vrange>(?:-?\d\.\d+(?:-(?:\d\.\d+)?)?)?) # version range
    \s*
    (?P<dependency>(?:[a-z][^;]*)?)              # Debian dependency
    (?:  # optional upstream version -> Debian version translator
        ;\s*
        (?P<standard>PEP386|PEP440)?             # PEP-386 / PEP-440 mode
        \s*
        (?P<rules>(?:s|tr|y).*)?                 # translator rules
    )?
    """, re.VERBOSE)
REQUIRES_RE = re.compile(r'''
    (?P<name>[A-Za-z][A-Za-z0-9_.-]*)    # Python distribution name
    \s*
    (?P<enabled_extras>(?:\[[^\]]*\])?)  # ignored for now
    \s*
    \(?  # optional parenthesis
    (?:  # optional minimum/maximum version
        (?P<operator><=?|>=?|==|!=|~=)
        \s*
        (?P<version>(\w|[-.*])+)
        (?:  # optional interval minimum/maximum version
            \s*
            ,
            \s*
            (?P<operator2><=?|>=?|==|!=)
            \s*
            (?P<version2>(\w|[-.])+)
        )?
    )?
    \)?  # optional closing parenthesis
    \s*
    (?:;  # optional environment markers
        (?P<environment_marker>.+)
    )?
    ''', re.VERBOSE)
EXTRA_RE = re.compile(r'''
    ;
    \s*
    extra
    \s*
    ==
    \s*
    (?P<quote>['"])
    (?P<section>[a-zA-Z0-9-_.]+)
    (?P=quote)
    ''', re.VERBOSE)
REQ_SECTIONS_RE = re.compile(r'''
    ^
    \[
    (?P<section>[a-zA-Z0-9-_.]+)?
    \s*
    (?::
        (?P<environment_marker>.+)
    )?
    \]
    \s*
    $
    ''', re.VERBOSE)
DEB_VERS_OPS = {
    '==': '=',
    '<':  '<<',
    '>':  '>>',
    '~=': '>=',
}
# Optimize away any dependencies on Python less than:
MIN_PY_VERSION = [3, 11]


class Standard(StrEnum):
    PEP386 = "PEP386"
    PEP440 = "PEP440"


class ModificationAction(Enum):
    SKIP = auto()
    KEEP = auto()
    APPEND = auto()


class RequirementModification(NamedTuple):
    action: ModificationAction
    alternative: str | None = None


def validate(fpath: str) -> bool:
    """Check if pydist file looks good."""
    with open(fpath, encoding='utf-8') as fp:
        for line in fp:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            if not PYDIST_RE.match(line):
                log.error('invalid pydist data in file %s: %s',
                          fpath.rsplit('/', 1)[-1], line)
                return False
    return True


class PyDist(TypedDict):
    name: str
    versions: set[Version]
    dependency: str
    standard: Standard | None
    rules: list[str]


@cache
def load(impl: str) -> dict[str, list[PyDist]]:
    """Load information about installed Python distributions.

    :param impl: interpreter implementation, f.e. cpython3
    :type impl: str
    """
    fname = PYDIST_OVERRIDES_FNAMES.get(impl)
    if fname and exists(fname):
        to_check = [fname]  # first one!
    else:
        to_check = []

    dname = PYDIST_DIRS.get(impl)
    if dname and isdir(dname):
        to_check.extend(join(dname, i) for i in os.listdir(dname))

    fbdir = os.environ.get('DH_PYTHON_DIST', '/usr/share/dh-python/dist/')
    fbname = join(fbdir, '{}_fallback'.format(impl))
    if exists(fbname):  # fall back generated at dh-python build time
        to_check.append(fbname)  # last one!

    result: dict[str, list[PyDist]] = {}
    for fpath in to_check:
        assert fpath
        with open(fpath, encoding='utf-8') as fp:
            for line in fp:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                if not (m := PYDIST_RE.search(line)):
                    raise Exception('invalid pydist line: %s (in %s)' % (line, fpath))
                data = m.groupdict()
                dist = PyDist(
                    name=normalize_name(data['name']),
                    versions=get_requested_versions(impl, data['vrange']),
                    dependency=data['dependency'].strip(),
                    rules=data['rules'].split(';') if data["rules"] else [],
                    standard=cast(Standard | None, data['standard'])
                )
                result.setdefault(dist["name"], []).append(dist)
    return result


def guess_dependency(
    impl: str,
    req: str,
    version: Version | str | None = None,
    bdep: BD | None = None,
    accept_upstream_versions: bool = False
) -> str | None:
    bdep = bdep or {}
    log.debug('trying to find dependency for %s (python=%s)',
              req, version)
    if isinstance(version, str):
        version = Version(version)

    # some upstreams have weird ideas for distribution name...
    if not (m := re.compile(r'([^!><=~ \(\)\[;]+)(.*)').match(req)):
        raise Exception(f"Unable to parse requirement: {req}")
    name, rest = m.groups()
    # TODO: check stdlib and dist-packaged for name.py and name.so files
    req = normalize_name(name) + rest

    data = load(impl)
    if not (m := REQUIRES_RE.match(req)):
        log.info('please ask dh_python3 author to fix REQUIRES_RE '
                 'or your upstream author to fix requires.txt')
        raise Exception(f'requirement is not valid: {req}')
    req_d: dict[str, str] = m.groupdict()

    env_marker_alts = ''
    if req_d['environment_marker']:
        modification = check_environment_marker_restrictions(
            req,
            req_d['environment_marker'],
            impl)
        if modification.action == ModificationAction.SKIP:
            return None
        elif modification.action == ModificationAction.KEEP:
            pass
        elif modification.action == ModificationAction.APPEND:
            assert modification.alternative
            env_marker_alts = ' | ' + modification.alternative

    name = req_d['name']
    details = data.get(normalize_name(name))
    if details:
        log.debug("dependency: module %s is known to pydist: %r", name, details)
        for item in details:
            if version and version not in item.get('versions', version):
                # rule doesn't match version, try next one
                continue
            if not item['dependency']:
                log.debug("dependency: requirement ignored")
                return None  # this requirement should be ignored
            if item['dependency'].endswith(')'):
                # no need to translate versions if version is hardcoded in
                # Debian dependency
                log.debug("dependency: requirement already has hardcoded version")
                return item['dependency'] + env_marker_alts
            if req_d['operator'] == '==' and req_d['version'].endswith('*'):
                # Translate "== 1.*" to "~= 1.0"
                req_d['operator'] = '~='
                req_d['version'] = req_d['version'].replace('*', '0')
                log.debug("dependency: translated wildcard version to semver limit")
            if req_d['version'] and (item['standard'] or item['rules']) and\
                    req_d['operator'] not in (None, '!='):
                o = _translate_op(req_d['operator'])
                v = _translate(req_d['version'], item['rules'], item['standard'])
                if req_d['operator'] == '==' and req_d['operator2'] is None:
                    # Loosen for Debian revisions
                    m = re.search(r"(.*)(\d+)(\D*)$", v)
                    if m:
                        max_v = m.group(1) + str((int(m.group(2))) + 1) + m.group(3) + "~"
                    else:
                        max_v = v + ".0~"
                    d = "%s (>= %s)%s, %s (<< %s)%s" % (
                        item['dependency'], v, env_marker_alts,
                        item['dependency'], max_v, env_marker_alts,
                    )
                else:
                    d = "%s (%s %s)%s" % (
                        item['dependency'], o, v, env_marker_alts)
                if req_d['version2'] and req_d['operator2'] not in (None, '!='):
                    o2 = _translate_op(req_d['operator2'])
                    v2 = _translate(req_d['version2'], item['rules'], item['standard'])
                    d += ", %s (%s %s)%s" % (
                        item['dependency'], o2, v2, env_marker_alts)
                elif req_d['operator'] == '~=':
                    o2 = '<<'
                    v2 = _translate(_max_compatible(req_d['version']), item['rules'], item['standard'])
                    d += ", %s (%s %s)%s" % (
                        item['dependency'], o2, v2, env_marker_alts)
                log.debug("dependency: constructed version")
                return d
            elif accept_upstream_versions and req_d['version'] and \
                    req_d['operator'] not in (None,'!='):
                o = _translate_op(req_d['operator'])
                d = "%s (%s %s)%s" % (
                    item['dependency'], o, req_d['version'], env_marker_alts)
                if req_d['version2'] and req_d['operator2'] not in (None,'!='):
                    o2 = _translate_op(req_d['operator2'])
                    d += ", %s (%s %s)%s" % (
                        item['dependency'], o2, req_d['version2'],
                        env_marker_alts)
                elif req_d['operator'] == '~=':
                    o2 = '<<'
                    d += ", %s (%s %s)%s" % (
                        item['dependency'], o2,
                        _max_compatible(req_d['version']), env_marker_alts)
                log.debug("dependency: constructed upstream version")
                return d
            else:
                if item['dependency'] in bdep:
                    if None in bdep[item['dependency']] and bdep[item['dependency']][None]:
                        log.debug("dependency: included in build-deps with limits ")
                        return "{} ({}){}".format(
                            item['dependency'], bdep[item['dependency']][None],
                            env_marker_alts)
                    # if arch in bdep[item['dependency']]:
                    # TODO: handle architecture specific dependencies from build depends
                    #       (current architecture is needed here)
                log.debug("dependency: included in build-deps")
                return item['dependency'] + env_marker_alts

    # search for Egg metadata file or directory (using dpkg -S)
    dpkg_query_tpl, regex_filter = PYDIST_DPKG_SEARCH_TPLS[impl]
    dpkg_query = dpkg_query_tpl.format(ci_regexp(normalize_name(name)))

    log.debug("invoking dpkg -S %s", dpkg_query)
    process = subprocess.run(
        ('/usr/bin/dpkg', '-S', dpkg_query),
        check=False, encoding="UTF-8", capture_output=True,
    )
    if process.returncode == 0:
        result = set()
        for line in process.stdout.split('\n'):
            if not line.strip():
                continue
            pkg, path = line.split(':', 1)
            if regex_filter and not re.search(regex_filter, path):
                continue
            result.add(pkg)
        if len(result) > 1:
            log.error('more than one package name found for %s dist', name)
        elif not result:
            log.debug('dpkg -S did not find package for %s', name)
        else:
            log.debug('dependency: found a result with dpkg -S')
            return result.pop() + env_marker_alts
    else:
        log.debug('dpkg -S did not find package for %s: %s', name, process.stderr)

    pname = sensible_pname(impl, normalize_name(name))
    log.info('Cannot find package that provides %s. '
             'Please add package that provides it to Build-Depends or '
             'add "%s %s" line to %s or add proper '
             'dependency to Depends by hand and ignore this info.',
             name, normalize_name(name), pname, PYDIST_OVERRIDES_FNAMES[impl])
    return None


def check_environment_marker_restrictions(
    req: str, marker_str: str, impl: str
) -> RequirementModification:
    """Should we keep or skip a dependency based on its environment markers."""
    if impl != 'cpython3':
        log.info('Ignoring environment markers for non-Python 3.x: %s', req)
        return RequirementModification(action=ModificationAction.SKIP)

    try:
        marker, op, value = parse_environment_marker(marker_str)
    except ComplexEnvironmentMarker:
        log.info('Ignoring complex environment marker: %s', req)
        return RequirementModification(action=ModificationAction.SKIP)

    # TODO: Use dynamic values when building arch-dependent
    # binaries, otherwise static values
    # TODO: Hurd values?
    supported_values = {
        'implementation_name': ('cpython', 'pypy'),
        'os_name': ('posix',),
        'platform_system': ('GNU/kFreeBSD', 'Linux'),
        'platform_machine': (platform.machine(),),
        'platform_python_implementation': ('CPython', 'PyPy'),
        'sys_platform': (
            'gnukfreebsd8', 'gnukfreebsd9', 'gnukfreebsd10',
            'gnukfreebsd11', 'gnukfreebsd12', 'gnukfreebsd13',
            'linux'),
    }
    if marker in supported_values:
        sv = supported_values[marker]
        if op in ('==', '!='):
            if ((op == '==' and value not in sv)
                    or (op == '!=' and value in sv)):
                log.debug('Skipping requirement (%s != %s): %s',
                          value, sv, req)
                return RequirementModification(action=ModificationAction.SKIP)
        else:
            log.info(
                'Skipping requirement with unhandled environment marker '
                'comparison: %s', req)
            return RequirementModification(action=ModificationAction.SKIP)

    elif marker in ('python_version', 'python_full_version',
                        'implementation_version'):
        # TODO: Replace with full PEP-440 parser
        env_ver = value
        split_ver = value.split('.')
        if marker == 'python_version':
            version_parts = 2
        elif marker == 'python_full_version':
            version_parts = 3
        else:
            version_parts = len(split_ver)

        if '*' in env_ver:
            if split_ver.index('*') != len(split_ver) -1:
                log.info('Skipping requirement with intermediate wildcard: %s',
                         req)
                return RequirementModification(action=ModificationAction.SKIP)
            split_ver.pop()
            env_ver = '.'.join(split_ver)
            if op == '==':
                if marker == 'python_full_version':
                    marker = 'python_version'
                    version_parts = 2
            elif op == '!=':
                if marker == 'python_full_version':
                    marker = 'python_version'
                    version_parts = 2
                else:
                    log.info('Ignoring wildcard != requirement, not '
                             'representable in Debian: %s', req)
                    return RequirementModification(
                        action=ModificationAction.KEEP
                    )
            else:
                log.info('Skipping requirement with %s on a wildcard: %s',
                         op, req)
                return RequirementModification(action=ModificationAction.SKIP)

        int_ver = []
        for ver_part in split_ver:
            if ver_part.isdigit():
                int_ver.append(int(ver_part))
            else:
                env_ver = '.'.join(str(x) for x in int_ver)
                log.info('Truncating unparseable version %s to %s in %s',
                         value, env_ver, req)
                break

        if len(int_ver) < version_parts:
            int_ver.append(0)
            env_ver += '.0'
        int_next_ver = int_ver.copy()
        int_next_ver[version_parts - 1] += 1
        next_ver = '.'.join(str(x) for x in int_next_ver)
        #int_prev_ver = int_ver.copy()
        #int_prev_ver[version_parts - 1] -= 1
        #prev_ver = '.'.join(str(x) for x in int_prev_ver)

        # We try to do something somewhat sensible with micro versions
        # even though we don't currently emit them in python3-supported-min/max

        if op == '<':
            if int_ver <= MIN_PY_VERSION:
                return RequirementModification(action=ModificationAction.SKIP)
            return RequirementModification(
                action=ModificationAction.APPEND,
                alternative=f'python3-supported-min (>= {env_ver})',
            )
        elif op == '<=':
            return RequirementModification(
                action=ModificationAction.APPEND,
                alternative=f'python3-supported-min (>> {env_ver})',
            )
        elif op == '>=':
            if int_ver < MIN_PY_VERSION:
                return RequirementModification(action=ModificationAction.KEEP)
            return RequirementModification(
                action=ModificationAction.APPEND,
                alternative=f'python3-supported-max (<< {env_ver})',
            )
        elif op == '>':
            if int_ver < MIN_PY_VERSION:
                return RequirementModification(action=ModificationAction.KEEP)
            return RequirementModification(
                action=ModificationAction.APPEND,
                alternative=f'python3-supported-max (<= {env_ver})',
            )
        elif op == '==':
            if marker == 'python_version':
                return RequirementModification(
                    action=ModificationAction.APPEND,
                    alternative=(
                        f'python3-supported-max (<< {env_ver}) '
                        f'| python3-supported-min (>= {next_ver})'
                    )
                )
            return RequirementModification(
                action=ModificationAction.APPEND,
                alternative=(
                    f'python3-supported-max (<< {env_ver}) '
                    f'| python3-supported-min (>> {env_ver})'
                )
            )
        elif op == '===':
            # === is arbitrary equality (PEP 440)
            if marker == 'python_version':
                return RequirementModification(
                    action=ModificationAction.APPEND,
                    alternative=(
                        f'python3-supported-max (<< {env_ver}) '
                        f'| python3-supported-min (>> {env_ver})'
                    )
                )
            else:
                log.info(
                    'Skipping requirement with %s environment marker, cannot '
                    'model in Debian deps: %s', op, req)
                return RequirementModification(action=ModificationAction.SKIP)
        elif op == '~=':  # Compatible equality (PEP 440)
            int_ceq_next_ver = int_ver[:2]
            int_ceq_next_ver[1] += 1
            ceq_next_ver = '.'.join(str(x) for x in int_ceq_next_ver)
            return RequirementModification(
                action=ModificationAction.APPEND,
                alternative=(
                    f'python3-supported-max (<< {env_ver}) '
                    f'| python3-supported-min (>= {ceq_next_ver})'
                )
            )
        elif op == '!=':
            log.info('Ignoring != comparison in environment marker, cannot '
                     'model in Debian deps: %s', req)
            return RequirementModification(action=ModificationAction.KEEP)

    elif marker == 'extra':
        # Handled in section logic of parse_requires_dist()
        return RequirementModification(action=ModificationAction.KEEP)
    else:
        log.info('Skipping requirement with unknown environment marker: %s',
                 marker)
        return RequirementModification(action=ModificationAction.SKIP)
    return RequirementModification(action=ModificationAction.KEEP)


class NewDependencies(TypedDict):
    depends: list[str]
    recommends: list[str]
    suggests: list[str]


def parse_pydep(
    impl: str,
    fname: str,
    bdep: BD | None = None,
    *,
    options: Namespace | None = None,
    depends_sec: list[str] | None = None,
    recommends_sec: list[str] | None = None,
    suggests_sec: list[str] | None = None,
) -> NewDependencies:
    depends_sec = depends_sec or []
    recommends_sec = recommends_sec or []
    suggests_sec = suggests_sec or []

    public_dir = PUBLIC_DIR_RE[impl].match(fname)
    ver = None
    if public_dir and public_dir.groups() and len(public_dir.group(1)) != 1:
        ver = public_dir.group(1)

    guess_deps = partial(guess_dependency, impl=impl, version=ver, bdep=bdep,
                         accept_upstream_versions=getattr(
                             options, 'accept_upstream_versions', False))

    result = NewDependencies(depends=[], recommends=[], suggests=[])
    modified: bool = False
    section: str | None = None
    modification = RequirementModification(action=ModificationAction.KEEP)
    processed = []
    with open(fname, 'r', encoding='utf-8') as fp:
        for line in fp:
            line = line.strip()
            if not line or line.startswith('#'):
                processed.append(line)
                continue
            if line.startswith('['):
                m = REQ_SECTIONS_RE.match(line)
                if not m:
                    log.info('Skipping section %s, unable to parse header',
                             line)
                    processed.append(line)
                    # something that won't map to a result_key
                    section = '[non-existent section]'
                    continue
                section = m.group('section')
                modification = RequirementModification(
                    action=ModificationAction.KEEP
                )
                if m.group('environment_marker'):
                    modification = check_environment_marker_restrictions(
                        line,
                        m.group('environment_marker'),
                        impl)
                processed.append(line)
                continue
            result_key: Literal["depends", "recommends", "suggests"]
            if section:
                if section in depends_sec:
                    result_key = 'depends'
                elif section in recommends_sec:
                    result_key = 'recommends'
                elif section in suggests_sec:
                    result_key = 'suggests'
                else:
                    processed.append(line)
                    continue
            else:
                result_key = 'depends'

            dependency = None
            if modification.action != ModificationAction.SKIP:
                dependency = guess_deps(req=line)
            if dependency and modification.action == ModificationAction.APPEND:
                assert modification.alternative
                dependency = ', '.join(
                    part.strip() + ' | ' + modification.alternative
                    for part in dependency.split(','))

            if dependency:
                result[result_key].append(dependency)
                modified = True
            else:
                processed.append(line)
    if modified and public_dir:
        with open(fname, 'w', encoding='utf-8') as fp:
            fp.writelines(i + '\n' for i in processed)
    return result


def parse_requires_dist(
    impl: str,
    fname: str,
    bdep: BD | None = None,
    *,
    options: Namespace | None = None,
    depends_sec: list[str] | None = None,
    recommends_sec: list[str] | None = None,
    suggests_sec: list[str] | None = None,
) -> NewDependencies:
    """Extract dependencies from a dist-info/METADATA file"""
    depends_sec = depends_sec or []
    recommends_sec = recommends_sec or []
    suggests_sec = suggests_sec or []

    public_dir = PUBLIC_DIR_RE[impl].match(fname)
    ver = None
    if public_dir and public_dir.groups() and len(public_dir.group(1)) != 1:
        ver = public_dir.group(1)

    guess_deps = partial(guess_dependency, impl=impl, version=ver, bdep=bdep,
                         accept_upstream_versions=getattr(
                             options, 'accept_upstream_versions', False))
    result = NewDependencies(depends=[], recommends=[], suggests=[])
    section = None
    with open(fname, 'r', encoding='utf-8') as fp:
        metadata = email.message_from_string(fp.read())
    requires = metadata.get_all('Requires-Dist', [])
    result_key: Literal["depends", "recommends", "suggests"]
    for req in requires:
        m = EXTRA_RE.search(req)
        result_key = 'depends'
        if m:
            section = m.group('section')
            if section:
                if section in depends_sec:
                    result_key = 'depends'
                elif section in recommends_sec:
                    result_key = 'recommends'
                elif section in suggests_sec:
                    result_key = 'suggests'
                else:
                    continue
        dependency = guess_deps(req=req)
        if dependency:
            result[result_key].append(dependency)
    return result


# https://packaging.python.org/en/latest/specifications/simple-repository-api/#normalized-names
def normalize_name(name: str) -> str:
    """Normalize a distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def sensible_pname(impl: str, dist_name: str) -> str:
    """Guess Debian package name from normalized distribution name."""
    dist_name = dist_name.removeprefix("python-")
    return f"{PKG_PREFIX_MAP[impl]}-{dist_name}"


def ci_regexp(name: str) -> str:
    """Return case insensitive dpkg -S regexp."""
    return ''.join("[%s%s]" % (i.upper(), i) if i.isalpha() else i for i in name.lower())


PEP386_PRE_VER_RE = re.compile(r'[-.]?(alpha|beta|rc|dev|a|b|c)')
PEP440_PRE_VER_RE = re.compile(r'[-.]?(a|b|rc)')
GROUP_RE = re.compile(r'\$(\d+)')


def _pl2py(pattern: str) -> str:
    r"""Convert Perl RE patterns used in uscan to Python's

    >>> print(_pl2py('foo$3'))
    foo\g<3>
    """
    return GROUP_RE.sub(r'\\g<\1>', pattern)


def _max_compatible(version: str) -> str:
    """Return the maximum version compatible with `version` in PEP440 terms,
    used by ~= requires version specifiers.

    https://www.python.org/dev/peps/pep-0440/#compatible-release

    >>> _max_compatible('2.2')
    '3'
    >>> _max_compatible('1.4.5')
    '1.5'
    >>> _max_compatible('1.3.alpha4')
    '2'
    >>> _max_compatible('2.1.3.post5')
    '2.2'

    """
    v = Version(version)
    v.serial = None
    v.releaselevel = None
    if v.micro is not None:
        v.micro = None
        return str(v + 1)
    v.minor = None
    return str(v + 1)


def _translate(
    version: str, rules: list[str], standard: Standard | None
) -> str:
    """Translate Python version into Debian one.

    >>> _translate('1.C2betac', ['s/c//gi'], None)
    '1.2beta'
    >>> _translate('5-fooa1.2beta3-fooD',
    ...     ['s/^/1:/', 's/-foo//g', 's:([A-Z]):+$1:'], 'PEP386')
    '1:5~a1.2~beta3+D'
    >>> _translate('x.y.x.z', ['tr/xy/ab/', 'y,z,Z,'], None)
    'a.b.a.Z'
    """
    for rule in rules:
        # uscan supports s, tr and y operations
        if rule.startswith(('tr', 'y')):
            # Note: no support for escaped separator in the pattern
            pos = 1 if rule.startswith('y') else 2
            tmp = rule[pos + 1:].split(rule[pos])
            version = version.translate(str.maketrans(tmp[0], tmp[1]))
        elif rule.startswith('s'):
            # uscan supports: g, u and x flags
            tmp = rule[2:].split(rule[1])
            pattern = re.compile(tmp[0])
            count = 1
            if tmp[2:]:
                flags = tmp[2]
                if 'g' in flags:
                    count = 0
                if 'i' in flags:
                    pattern = re.compile(tmp[0], re.I)
            version = pattern.sub(_pl2py(tmp[1]), version, count)
        else:
            log.warning('unknown rule ignored: %s', rule)
    if standard == Standard.PEP386:
        version = PEP386_PRE_VER_RE.sub(r'~\g<1>', version)
    elif standard == Standard.PEP440:
        version = PEP440_PRE_VER_RE.sub(r'~\g<1>', version)
    return version


def _translate_op(operator: str) -> str:
    """Translate Python version operator into Debian one.

    >>> _translate_op('==')
    '='
    >>> _translate_op('<')
    '<<'
    >>> _translate_op('<=')
    '<='
    """
    return DEB_VERS_OPS.get(operator, operator)


if __name__ == '__main__':
    impl = os.environ.get('IMPL', 'cpython3')
    for i in sys.argv[1:]:
        if os.path.isfile(i):
            try:
                print(', '.join(parse_pydep(impl, i)['depends']))
            except Exception as err:
                log.error('%s: cannot guess (%s)', i, err)
        else:
            try:
                print(guess_dependency(impl, i) or '')
            except Exception as err:
                log.error('%s: cannot guess (%s)', i, err)
