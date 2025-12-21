# Copyright © 2012-2013 Piotr Ożarowski <piotr@debian.org>
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
import os
import re
from os.path import exists, join
from pathlib import Path
from typing import ClassVar, NamedTuple, Self, TYPE_CHECKING

from dhpython import INTERPRETER_DIR_TPLS, PUBLIC_DIR_RE, OLD_SITE_DIRS

if TYPE_CHECKING:
    from typing import Literal


SHEBANG_RE = re.compile(
    r"""
    (?:\#!\s*){0,1}  # shebang prefix
    (?P<path>
        .*?/bin/.*?)?
    (?P<name>
        python|pypy)
    (?P<version>
        \d[\.\d]*)?
    (?P<debug>
        -dbg)?
    (?P<options>.*)
    """,
    re.VERBOSE,
)
EXTFILE_RE = re.compile(
    r"""
    (?P<name>.*?)
    (?:\.
        (?:
            (?P<stableabi>abi\d+)
            |(?P<soabi>
                (?P<impl>cpython|pypy)
                -
                (?P<ver>\d{2,})
                (?P<flags>[a-z]*)
            )
        )
        (?:
            -
            (?P<multiarch>[^/]*?)
        )?
    )?
    (?P<debug>_d)?
    \.so$""",
    re.VERBOSE,
)
log = logging.getLogger("dhpython")


class Shebang(NamedTuple):
    name: str
    path: str | None = None
    version: str | None = None
    debug: bool = False
    options: tuple[str, ...] = ()


class Interpreter:
    """
    :attr path: /usr/bin/ in most cases
    :attr name: pypy or python (even for python3 and python-dbg) or empty string
    :attr version: interpreter's version
    :attr debug: -dbg version of the interpreter
    :attr impl: implementation (cpython3 or pypy)
    :attr options: options parsed from shebang
    :type path: str
    :type name: str
    :type version: Version or None
    :type debug: bool
    :type impl: str
    :type options: tuple
    """

    path = "/usr/bin/"
    name = "python"
    version: "Version | None" = None
    debug = False
    impl = ""
    options: tuple[str, ...] = ()
    _cmd_cache: ClassVar[dict[str, list[str] | str]] = {}
    _re_cache: ClassVar[dict[str, re.Pattern[str]]] = {}

    def __init__(
        self,
        value: Self | str | None = None,
        *,
        path: str | None = None,
        name: str | None = None,
        version: str | None = None,
        debug: str | None = None,
        impl: str | None = None,
        options: str | None = None,
    ) -> None:
        # pylint: disable=unused-argument
        params = locals()
        del params["self"]
        del params["value"]

        if isinstance(value, Interpreter):
            for key in params.keys():
                if params[key] is None:
                    params[key] = getattr(value, key)
        elif value:
            if value.replace(".", "").isdigit() and not version:
                # version string
                params["version"] = Version(value)
            else:
                # shebang or other string
                shebang = self.parse(value)
                assert shebang
                for key, val in shebang._asdict().items():
                    # prefer values passed to constructor over shebang ones:
                    if params[key] is None:
                        params[key] = val

        for key, val in params.items():
            if val is not None:
                setattr(self, key, val)
            elif key == "version":
                setattr(self, key, val)

    def __setattr__(self, name: str, value: "str | Version | None") -> None:
        if name == "name":
            if value not in ("python", "pypy", ""):
                raise ValueError("interpreter not supported: %s" % value)
            if value == "python":
                if self.version:
                    if self.version.major == 3:
                        self.__dict__["impl"] = "cpython3"
            elif value == "pypy":
                if self.version:
                    if self.version.major == 3:
                        self.__dict__["impl"] = "pypy3"
        elif name == "version" and value is not None:
            value = Version(value)
            if not self.impl and self.name == "python":
                if value.major == 3:
                    self.impl = "cpython3"
        if name in ("path", "name", "impl", "options") and value is None:
            pass
        elif name == "debug":
            self.__dict__[name] = bool(value)
        else:
            self.__dict__[name] = value

    def __repr__(self) -> str:
        result = self.path
        if not result.endswith("/"):
            result += "/"
        result += self._vstr(self.version)
        if self.options:
            result += " " + " ".join(self.options)
        return result

    def __str__(self) -> str:
        return self._vstr(self.version)

    def _vstr(
        self, version: "str | Version | None" = None, consider_default_ver: bool = False
    ) -> str:
        if self.impl == "pypy":
            # TODO: will Debian support more than one PyPy version?
            return self.name
        version = version or self.version or ""
        if consider_default_ver and (not version or version == self.default_version):
            version = "3"
        if self.debug:
            return "python{}-dbg".format(version)
        return self.name + str(version)

    def binary(self, version: "Version | None" = None) -> str:
        return "{}{}".format(self.path, self._vstr(version))

    @property
    def binary_dv(self) -> str:
        """Like binary(), but returns path to default intepreter symlink
        if version matches default one for given implementation.
        """
        return "{}{}".format(self.path, self._vstr(consider_default_ver=True))

    @property
    def default_version(self) -> "Version | None":
        if self.impl:
            return default(self.impl)
        return None

    @staticmethod
    def parse(shebang: str) -> Shebang | None:
        """Return dict with parsed shebang

        >>> Interpreter.parse('#!/usr/bin/python')
        Shebang(name='python', path='/usr/bin/', version='3', debug=False, options=())
        >>> Interpreter.parse('/usr/bin/python3.2-dbg')
        Shebang(name='python', path='/usr/bin/', version='3.2', debug=True, options=())
        >>> Interpreter.parse('#! /usr/bin/python3.2')
        Shebang(name='python', path='/usr/bin/', version='3.2', debug=False, options=())
        >>> Interpreter.parse('/usr/bin/python3.2-dbg --foo --bar')
        Shebang(name='python', path='/usr/bin/', version='3.2', debug=True, options=('--foo', '--bar'))
        """
        if not (m := SHEBANG_RE.search(shebang)):
            return None
        groups = m.groupdict()
        version = groups["version"]
        if version is None and groups["name"] == "python":
            version = "3"
        return Shebang(
            name=groups["name"],
            path=groups["path"],
            version=version,
            debug=bool(groups["debug"]),
            # TODO: do we need "--key value" here?
            options=tuple(groups["options"].split()),
        )

    @classmethod
    def from_file(cls, fpath: str | Path) -> "Interpreter":
        """Read file's shebang and parse it."""
        interpreter = Interpreter()
        with open(fpath, "rb") as fp:
            data = fp.read(96)
            if b"\0" in data:
                raise ValueError("cannot parse binary file")
        # make sure only first line is checked
        shebang = data.decode("utf-8").split("\n", maxsplit=1)[0]
        if not shebang.startswith("#!"):
            raise ValueError(f"doesn't look like a shebang: {shebang}")

        parsed = cls.parse(shebang)
        if not parsed:
            raise ValueError(f"doesn't look like a shebang: {shebang}")
        for key, val in parsed._asdict().items():
            setattr(interpreter, key, val)
        return interpreter

    def sitedir(
        self,
        package: str | None = None,
        version: "str | Version | None" = None,
        gdb: bool = False,
    ) -> str:
        """Return path to site-packages directory.

        Note that returned path is not the final location of .py files

        >>> i = Interpreter('python')
        >>> i.sitedir(version='3.1')
        '/usr/lib/python3/dist-packages/'
        >>> i.sitedir(version='3.1', gdb=True, package='python3-foo')
        'debian/python3-foo/usr/lib/debug/usr/lib/python3/dist-packages/'
        >>> i.sitedir(version=Version('3.2'))
        '/usr/lib/python3/dist-packages/'
        """
        try:
            version = Version(version or self.version)
        except Exception as err:
            raise ValueError("cannot find valid version: %s" % err)
        if version << Version("3.0"):
            raise ValueError(f"The version {version} is no longer supported")
        path = "/usr/lib/python3/dist-packages/"

        if gdb:
            path = "/usr/lib/debug%s" % path
        if package:
            path = "debian/%s%s" % (package, path)

        return path

    def old_sitedirs(
        self,
        package: str | None = None,
        version: "str | Version | None" = None,
        gdb: bool = False,
    ) -> list[str]:
        """Return deprecated paths to site-packages directories."""
        try:
            version = Version(version or self.version)
        except Exception as err:
            raise ValueError("cannot find valid version: %s" % err)
        result = []
        for item in OLD_SITE_DIRS.get(self.impl, []):
            if isinstance(item, str):
                result.append(item.format(version))
            else:
                res = item(version)
                if res is not None:
                    result.append(res)

        if gdb:
            result = ["/usr/lib/debug{}".format(i) for i in result]
            if self.impl.startswith("cpython"):
                result.append(
                    "/usr/lib/debug/usr/lib/pyshared/python{}".format(version)
                )
        if package:
            result = ["debian/{}{}".format(package, i) for i in result]

        return result

    def parse_public_dir(self, path: str) -> "Version | Literal[True] | None":
        """Return version assigned to site-packages path
        or True is it's unversioned public dir."""
        match = PUBLIC_DIR_RE[self.impl].match(path)
        if match:
            vers = match.group(1)
            if vers and vers[0]:
                return Version(vers)
            return True
        return None

    def should_ignore(self, path: str) -> bool:
        """Return True if path is used by another interpreter implementation."""
        if len(INTERPRETER_DIR_TPLS) == 1:
            return False
        cache_key = f"should_ignore_{self.impl}"
        if cache_key not in self.__class__._re_cache:
            expr = [v for k, v in INTERPRETER_DIR_TPLS.items() if k != self.impl]
            regexp = re.compile("|".join("({})".format(i) for i in expr))
            self.__class__._re_cache[cache_key] = regexp
        else:
            regexp = self.__class__._re_cache[cache_key]
        return bool(regexp.search(path))

    @property
    def include_dir(self) -> str:
        """Return INCLUDE_DIR path.

        >>> Interpreter('python3.8').include_dir       # doctest: +SKIP
        '/usr/include/python3.8'
        >>> Interpreter('python3.8-dbg').include_dir   # doctest: +SKIP
        '/usr/include/python3.8d'
        """
        try:
            result = self._get_config()[2]
            if result:
                return result
        except Exception:
            result = ""
            log.debug("cannot get include path", exc_info=True)
        result = "/usr/include/{}".format(self.name)
        version = self.version
        assert version
        if self.debug:
            if version >= "3.8":
                result += "d"
            elif version << "3.3":
                result += "_d"
            else:
                result += "dm"
        else:
            if version >= "3.8":
                pass
            elif version >> "3.2":
                result += "m"
            elif version == "3.2":
                result += "mu"
        return result

    @property
    def library_file(self) -> str:
        """Return libfoo.so file path."""
        libpl, ldlibrary = self._get_config()[3:5]
        if ldlibrary.endswith(".a"):
            # python3.1-dbg, python3.2, python3.2-dbg returned static lib
            ldlibrary = ldlibrary.replace(".a", ".so")
        if libpl and ldlibrary:
            return join(libpl, ldlibrary)
        raise Exception("cannot find library file for {}".format(self))

    def check_extname(self, fname: str, version: "Version | None" = None) -> str | None:
        """Return extension file name if file can be renamed."""
        if not version and not self.version:
            return None

        version = Version(version or self.version)

        if "/" in fname:
            fdir, fname = fname.rsplit("/", 1)  # in case full path was passed
        else:
            fdir = ""

        if not (m := EXTFILE_RE.search(fname)):
            return None
        info = m.groupdict()
        if info["ver"] and (not version or version.minor is None):
            # get version from soabi if version is not set of only major
            # version number is set
            version = Version("%s.%s" % (info["ver"][0], info["ver"][1]))

        if info["stableabi"] and version < Version("3.13"):
            # We added support for stableabi multiarch filenames in 3.13
            # (GH-122931)
            return None
        if info["debug"] and self.debug is False:
            # do not change Python 2.X extensions already marked as debug
            # (the other way around is acceptable)
            return None
        if (info["soabi"] or info["stableabi"]) and info["multiarch"]:
            # already tagged, nothing we can do here
            return None

        try:
            soabi, multiarch = self._get_config(version)[:2]
        except Exception:
            log.debug("cannot get soabi/multiarch", exc_info=True)
            return None

        if info["soabi"] and soabi and info["soabi"] != soabi:
            return None

        tmp_soabi = info["stableabi"] or info["soabi"] or soabi
        tmp_multiarch = info["multiarch"] or multiarch

        result = info["name"]
        if (
            result.endswith("module")
            and result not in ("module", "_module")
            and self.impl == "cpython3"
        ):
            result = result[:-6]

        if tmp_soabi:
            result = f"{result}.{tmp_soabi}"
        if tmp_multiarch and tmp_multiarch not in result:
            result = f"{result}-{tmp_multiarch}"

        result += ".so"
        if fname == result:
            return None
        return join(fdir, result)

    def suggest_pkg_name(self, name: str) -> str:
        """Suggest binary package name with for given library name

        >>> Interpreter('python3.1').suggest_pkg_name('foo')
        'python3-foo'
        >>> Interpreter('python3.8').suggest_pkg_name('foo_bar')
        'python3-foo-bar'
        >>> Interpreter('python3.8-dbg').suggest_pkg_name('bar')
        'python3-bar-dbg'
        """
        name = name.replace("_", "-")
        result = "python3-{}".format(name)
        if self.debug:
            result += "-dbg"
        return result

    def _get_config(self, version: "str | Version | None" = None) -> list[str]:
        version = Version(version or self.version)
        cmd = (
            'import sysconfig as s; print("__SEP__".join(i or "" '
            "for i in s.get_config_vars("
            '"SOABI", "MULTIARCH", "INCLUDEPY", "LIBPL", "LDLIBRARY")))'
        )
        output = self._execute(cmd, version)
        assert isinstance(output, str)
        conf_vars = output.split("__SEP__")
        if conf_vars[1] in conf_vars[0]:
            # Python >= 3.5 includes MILTIARCH in SOABI
            conf_vars[0] = conf_vars[0].replace("-%s" % conf_vars[1], "")
        try:
            conf_vars[1] = os.environ["DEB_HOST_MULTIARCH"]
        except KeyError:
            pass
        return conf_vars

    def _execute(
        self, command: str, version: "str | Version | None" = None, cache: bool = True
    ) -> list[str] | str:
        version = Version(version or self.version)
        exe = "{}{}".format(self.path, self._vstr(version))
        command = "{} -c '{}'".format(exe, command.replace("'", "'"))
        if cache and command in self.__class__._cmd_cache:
            return self.__class__._cmd_cache[command]
        if not exists(exe):
            raise Exception(
                "cannot execute command due to missing " "interpreter: %s" % exe
            )

        output = execute(command)
        if output.returncode != 0:
            log.debug(output.stderr)
            raise Exception(f"{command} failed with status code {output.returncode}")

        result: list[str] | str = output.stdout.splitlines()

        if len(result) == 1:
            result = result[0]

        if cache:
            self.__class__._cmd_cache[command] = result

        return result


# due to circular imports issue
from dhpython.tools import execute
from dhpython.version import Version, default
