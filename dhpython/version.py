# Copyright © 2010-2013 Piotr Ożarowski <piotr@debian.org>
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

import logging
import re
from collections.abc import Iterable
from typing import TypeAlias
from os.path import exists

from dhpython import _defaults

RANGE_PATTERN = r"(-)?(\d\.\d+)(?:(-)(\d\.\d+)?)?"
RANGE_RE = re.compile(RANGE_PATTERN)
VERSION_RE = re.compile(
    r"""
    (?P<major>\d+)\.?
    (?P<minor>\d+)?\.?
    (?P<micro>\d+)?[.\s]?
    (?P<releaselevel>alpha|beta|candidate|final)?[.\s]?
    (?P<serial>\d+)?""",
    re.VERBOSE,
)

log = logging.getLogger("dhpython")
Interpreter = None

V: TypeAlias = "str | Version | Iterable[int]"


class Version:
    major: int
    minor: int | None
    micro: int | None
    releaselevel: str | None
    serial: int | None

    # TODO: Upgrade to PEP-440
    def __init__(
        self,
        value: "V | None" = None,
        *,
        major: int | None = None,
        minor: int | None = None,
        micro: int | None = None,
        releaselevel: str | None = None,
        serial: int | None = None,
    ) -> None:
        # pylint: disable=too-many-positional-arguments
        """Construct a new instance.

        >>> Version(major=0, minor=0, micro=0, releaselevel=0, serial=0)
        Version('0.0')
        >>> Version('0.0')
        Version('0.0')
        """
        # pylint: disable=unused-argument
        if isinstance(value, (tuple, list)):
            value = ".".join(str(i) for i in value)
        if isinstance(value, Version):
            for name in ("major", "minor", "micro", "releaselevel", "serial"):
                setattr(self, name, getattr(value, name))
            return
        comp = locals()
        del comp["self"]
        del comp["value"]
        if value:
            assert isinstance(value, str)
            match = VERSION_RE.match(value)
            for name, value in match.groupdict().items() if match else []:
                if value is not None and comp[name] is None:
                    if name == "releaselevel":
                        comp[name] = value
                    else:
                        comp[name] = int(value)
        for name, value in comp.items():
            setattr(self, name, value)
        if self.major is None:
            raise ValueError("major component is required")

    def __str__(self) -> str:
        """Return major.minor or major string.

        >>> str(Version(major=3, minor=2, micro=1, releaselevel='final', serial=4))
        '3.2'
        >>> str(Version(major=2))
        '2'
        """
        result = str(self.major)
        if self.minor is not None:
            result += f".{self.minor}"
        return result

    def __hash__(self) -> int:
        return hash(repr(self))

    def __repr__(self) -> str:
        """Return full version string.

        >>> repr(Version(major=3, minor=2, micro=1, releaselevel='final', serial=4))
        "Version('3.2.1.final.4')"
        >>> repr(Version(major=2))
        "Version('2')"
        """
        result = f"Version('{self}"
        for name in ("micro", "releaselevel", "serial"):
            value = getattr(self, name)
            if not value:
                break
            result += f".{value}"
        return result + "')"

    def __add__(self, other: int | str) -> "Version":
        """Return next version.

        >>> Version('3.1') + 1
        Version('3.2')
        >>> Version('2') + '1'
        Version('3')
        """
        result = Version(self)
        if result.minor is None:
            result.major += int(other)
        else:
            result.minor += int(other)
        return result

    def __sub__(self, other: int | str) -> "Version":
        """Return previous version.

        >>> Version('3.1') - 1
        Version('3.0')
        >>> Version('3') - '1'
        Version('2')
        """
        result = Version(self)
        if result.minor is None:
            result.major -= int(other)
            new = result.major
        else:
            result.minor -= int(other)
            new = result.minor
        if new < 0:
            raise ValueError("cannot decrease version further")
        return result

    def __eq__(self, other: object) -> bool:
        try:
            other = Version(other)  # type: ignore
        except Exception:
            return False
        return self.__cmp(other) == 0

    def __lt__(self, other: object) -> bool:
        return self.__cmp(other) < 0

    def __le__(self, other: object) -> bool:
        return self.__cmp(other) <= 0

    def __gt__(self, other: object) -> bool:
        return self.__cmp(other) > 0

    def __ge__(self, other: object) -> bool:
        return self.__cmp(other) >= 0

    def __lshift__(self, other: V) -> bool:
        """Compare major.minor or major only (if minor is not set).

        >>> Version('2.6') << Version('2.7')
        True
        >>> Version('2.6') << Version('2.6.6')
        False
        >>> Version('3') << Version('2')
        False
        >>> Version('3.1') << Version('2')
        False
        >>> Version('2') << Version('3.2.1.alpha.3')
        True
        """
        if not isinstance(other, Version):
            other = Version(other)
        if self.minor is None or other.minor is None:
            return self.__cmp(other, ignore="minor") < 0
        else:
            return self.__cmp(other, ignore="micro") < 0

    def __rshift__(self, other: V) -> bool:
        """Compare major.minor or major only (if minor is not set).

        >>> Version('2.6') >> Version('2.7')
        False
        >>> Version('2.6.7') >> Version('2.6.6')
        False
        >>> Version('3') >> Version('2')
        True
        >>> Version('3.1') >> Version('2')
        True
        >>> Version('2.1') >> Version('3.2.1.alpha.3')
        False
        """
        if not isinstance(other, Version):
            other = Version(other)
        if self.minor is None or other.minor is None:
            return self.__cmp(other, ignore="minor") > 0
        else:
            return self.__cmp(other, ignore="micro") > 0

    def __cmp(self, other: object, ignore: str | None = None) -> int:
        if not isinstance(other, Version):
            try:
                other = Version(other)  # type: ignore
            except Exception:
                raise ValueError(f"Cannot compare Version with {other!r}")
        for name in ("major", "minor", "micro", "releaselevel", "serial"):
            if name == ignore:
                break
            if name == "releaselevel":
                rmap: dict[str | None, int] = {
                    "alpha": -3,
                    "beta": -2,
                    "candidate": -1,
                    "final": 0,
                }
                value1 = rmap.get(self.releaselevel, 0)
                value2 = rmap.get(other.releaselevel, 0)
            else:
                value1 = getattr(self, name) or 0
                value2 = getattr(other, name) or 0
            if value1 == value2:
                continue
            return (value1 > value2) - (value1 < value2)
        return 0


class VersionRange:
    minver: Version | None
    maxver: Version | None

    def __init__(
        self,
        value: str | None = None,
        minver: "V | None" = None,
        maxver: "V | None" = None,
    ) -> None:
        if minver:
            self.minver = Version(minver)
        else:
            self.minver = None
        if maxver:
            self.maxver = Version(maxver)
        else:
            self.maxver = None

        if value:
            minver, maxver = self.parse(value)
            if minver and self.minver is None:
                self.minver = minver
            if maxver and self.maxver is None:
                self.maxver = maxver

    def __bool__(self) -> bool:
        if self.minver is not None or self.maxver is not None:
            return True
        return False

    def __str__(self) -> str:
        """Return version range string from given range.

        >>> str(VersionRange(minver='3.4'))
        '3.4-'
        >>> str(VersionRange(minver='3.4', maxver='3.6'))
        '3.4-3.6'
        >>> str(VersionRange(minver='3.4', maxver='4.0'))
        '3.4-4.0'
        >>> str(VersionRange(maxver='3.7'))
        '-3.7'
        >>> str(VersionRange(minver='3.5', maxver='3.5'))
        '3.5'
        >>> str(VersionRange())
        '-'
        """
        if self.minver is None is self.maxver:
            return "-"
        if self.minver == self.maxver:
            return str(self.minver)
        elif self.minver is None:
            return f"-{self.maxver}"
        elif self.maxver is None:
            return f"{self.minver}-"
        else:
            return f"{self.minver}-{self.maxver}"

    def __repr__(self) -> str:
        """Return version range string.

        >>> repr(VersionRange('5.0-'))
        "VersionRange(minver='5.0')"
        >>> repr(VersionRange('3.0-3.5'))
        "VersionRange(minver='3.0', maxver='3.5')"
        """
        result = "VersionRange("
        if self.minver is not None:
            result += f"minver='{self.minver}'"
            if self.maxver is not None:
                result += ", "
        if self.maxver is not None:
            result += f"maxver='{self.maxver}'"
        return result + ")"

    @staticmethod
    def parse(value: str) -> tuple[Version | None, Version | None]:
        """Return minimum and maximum Python version from given range.

        >>> VersionRange.parse('3.0-')
        (Version('3.0'), None)
        >>> VersionRange.parse('3.1-3.13')
        (Version('3.1'), Version('3.13'))
        >>> VersionRange.parse('3.2-4.0')
        (Version('3.2'), Version('4.0'))
        >>> VersionRange.parse('-3.7')
        (None, Version('3.7'))
        >>> VersionRange.parse('3.2')
        (Version('3.2'), Version('3.2'))
        >>> VersionRange.parse('') == VersionRange.parse('-')
        True
        >>> VersionRange.parse('>= 4.0')
        (Version('4.0'), None)
        """
        if value in ("", "-"):
            return None, None

        match = RANGE_RE.match(value)
        if not match:
            try:
                minv, maxv = VersionRange._parse_pycentral(value)
            except Exception:
                raise ValueError("version range is invalid: %s" % value)
        else:
            groups = match.groups()

            if list(groups).count(None) == 3:  # only one version is allowed
                minv = Version(groups[1])
                return minv, minv

            minv_s: str | None = None
            maxv_s: str | None = None
            if groups[0]:  # maximum version only
                maxv_s = groups[1]
            else:
                minv_s = groups[1]
                maxv_s = groups[3]

            minv = Version(minv_s) if minv_s else None
            maxv = Version(maxv_s) if maxv_s else None

        if maxv and minv and minv > maxv:
            raise ValueError("version range is invalid: %s" % value)

        return minv, maxv

    @staticmethod
    def _parse_pycentral(value: str) -> tuple[Version | None, Version | None]:
        """Parse X-Python3-Version.

        >>> VersionRange._parse_pycentral('>= 3.10')
        (Version('3.10'), None)
        >>> VersionRange._parse_pycentral('<< 4.0')
        (None, Version('4.0'))
        >>> VersionRange._parse_pycentral('3.1')
        (Version('3.1'), Version('3.1'))
        >>> VersionRange._parse_pycentral('3.1, 3.2')
        (Version('3.1'), None)
        """

        minv = maxv = None
        hardcoded = set()

        for item in value.split(","):
            item = item.strip()

            match = re.match(r">=\s*([\d\.]+)", item)
            if match:
                minv = match.group(1)
                continue
            match = re.match(r"<<\s*([\d\.]+)", item)
            if match:
                maxv = match.group(1)
                continue
            match = re.match(r"^[\d\.]+$", item)
            if match:
                hardcoded.add(match.group(0))

        if len(hardcoded) == 1:
            ver = hardcoded.pop()
            return Version(ver), Version(ver)

        if not minv and hardcoded:
            # yeah, no maxv!
            minv = sorted(hardcoded)[0]

        return Version(minv) if minv else None, Version(maxv) if maxv else None


def default(impl: str) -> Version:
    """Return default interpreter version for given implementation."""
    if impl not in _defaults.DEFAULT:
        raise ValueError("interpreter implementation not supported: %r" % impl)
    ver = _defaults.DEFAULT[impl]
    return Version(major=ver[0], minor=ver[1])


def supported(impl: str) -> list[Version]:
    """Return list of supported interpreter versions for given implementation."""
    if impl not in _defaults.SUPPORTED:
        raise ValueError("interpreter implementation not supported: %r" % impl)
    versions = _defaults.SUPPORTED[impl]
    return [Version(major=v[0], minor=v[1]) for v in versions]


def get_requested_versions(
    impl: str,
    vrange: VersionRange | str | None = None,
    available: bool | None = None,
) -> set[Version]:
    """Return a set of requested and supported Python versions.

    :param impl: interpreter implementation
    :param available: if set to `True`, return installed versions only,
        if set to `False`, return requested versions that are not installed.
        By default returns all requested versions.
    :type available: bool

    >>> sorted(get_requested_versions('cpython3', '')) == sorted(supported('cpython3'))
    True
    >>> sorted(get_requested_versions('cpython3', '-')) == sorted(supported('cpython3'))
    True
    >>> get_requested_versions('cpython3', '>= 5.0')
    set()
    """
    from dhpython.interpreter import Interpreter

    parsed_vrange: VersionRange | None = None
    if isinstance(vrange, str):
        parsed_vrange = VersionRange(vrange)

    if not parsed_vrange:
        versions = set(supported(impl))
    else:
        minv = (
            Version(major=0, minor=0)
            if parsed_vrange.minver is None
            else parsed_vrange.minver
        )
        maxv = (
            Version(major=99, minor=99)
            if parsed_vrange.maxver is None
            else parsed_vrange.maxver
        )
        if minv == maxv:
            versions = set([minv] if minv in supported(impl) else tuple())
        else:
            versions = {v for v in supported(impl) if minv <= v < maxv}

    if available:
        interpreter = Interpreter(impl=impl)
        versions = {v for v in versions if exists(interpreter.binary(v))}
    elif available is False:
        interpreter = Interpreter(impl=impl)
        versions = {v for v in versions if not exists(interpreter.binary(v))}

    return versions


def build_sorted(
    versions: Iterable[V],
    impl: str = "cpython3",
) -> list[Version]:
    """Return sorted list of versions in a build friendly order.

    i.e. default version, if among versions, is sorted last.

    >>> build_sorted([(2, 6), (3, 4), default('cpython3'), (3, 6), (2, 7)])[-1] == default('cpython3')
    True
    >>> build_sorted(('3.2', (3, 0), '3.1'))
    [Version('3.0'), Version('3.1'), Version('3.2')]
    """
    default_ver = default(impl)

    result = sorted(Version(v) for v in versions)
    try:
        result.remove(default_ver)
    except ValueError:
        pass
    else:
        result.append(default_ver)
    return result
