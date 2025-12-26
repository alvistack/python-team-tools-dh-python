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

import errno
import logging
import re
from dataclasses import dataclass
from os import makedirs, chmod, environ
from os.path import basename, exists, join, dirname
from sys import argv
from typing import NamedTuple, TypeAlias

from dhpython import DEPENDS_SUBSTVARS, PKG_NAME_TPLS, RT_LOCATIONS, RT_TPLS


log = logging.getLogger("dhpython")
parse_dep = re.compile(
    r"""[,\s]*
    (?P<name>[^\s:]+)(?::any)?
    \s*
    \(?(?P<version>([>=<]{2,}|=)\s*[^\)]+)?\)?
    \s*
    (?:\[(?P<arch>[^\]]+)\])?
    """,
    re.VERBOSE,
).match


@dataclass
class PackageData:
    substvars: dict[str, list[str]]
    autoscripts: dict[str, dict[str, list[str]]]
    rtupdates: list[tuple[str, str]]
    arch: str


class Options(NamedTuple):
    arch: bool | None
    package: list[str]
    no_package: list[str]
    write_log: bool
    compile_all: bool
    remaining_packages: bool


def build_options(
    *,
    arch: bool | None = None,
    package: list[str] | None = None,
    no_package: list[str] | None = None,
    write_log: bool = False,
    compile_all: bool = False,
    remaining_packages: bool = False,
) -> Options:
    return Options(
        arch=arch,
        compile_all=compile_all,
        package=package or [],
        no_package=no_package or [],
        write_log=write_log,
        remaining_packages=remaining_packages,
    )


BD: TypeAlias = dict[str, dict[str | None, str]]


class DebHelper:
    """Reinvents the wheel / some dh functionality (Perl is ugly ;-P)"""

    options: Options
    packages: dict[str, PackageData]
    build_depends: BD

    def __init__(self, options: Options, impl: str = "cpython3") -> None:
        self.options = options
        self.packages = {}
        self.build_depends = {}
        self.python_version = None
        self.impl = impl
        self.command = {
            "cpython3": "dh_python3",
        }[impl]
        skip_tpl_set: set[str] = set()
        for name, tpls in PKG_NAME_TPLS.items():
            if name != impl:
                skip_tpl_set.update(tpls)
        skip_tpl = tuple(skip_tpl_set)
        substvar = DEPENDS_SUBSTVARS[impl]

        pkgs = options.package
        skip_pkgs = options.no_package

        try:
            with open("debian/control", encoding="utf-8") as fp:
                paragraphs: list[dict[str, str]] = [{}]
                field = None
                for lineno, line in enumerate(fp, 1):
                    if line.startswith("#"):
                        continue
                    if not line.strip():
                        if paragraphs[-1]:
                            paragraphs.append({})
                            field = None
                        continue
                    if line[0].isspace():  # Continuation
                        assert field
                        paragraphs[-1][field] += line.rstrip()
                        continue
                    if not ":" in line:
                        raise Exception(
                            "Unable to parse line %i in debian/control: %s"
                            % (lineno, line)
                        )
                    field, value = line.split(":", 1)
                    field = field.lower()
                    paragraphs[-1][field] = value.strip()
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise Exception("cannot find debian/control file")
            raise

        # Trailing new lines?
        if not paragraphs[-1]:
            paragraphs.pop()

        if len(paragraphs) < 2:
            raise Exception(
                "Unable to parse debian/control, found less than 2 paragraphs"
            )

        self.source_name = paragraphs[0]["source"]
        if self.impl == "cpython3" and "x-python3-version" in paragraphs[0]:
            self.python_version = paragraphs[0]["x-python3-version"]
            if len(self.python_version.split(",")) > 2:
                raise ValueError(
                    "too many arguments provided for "
                    "X-Python3-Version: min and max only."
                )

        build_depends_list = []
        for field in ("build-depends", "build-depends-indep", "build-depends-arch"):
            if field in paragraphs[0]:
                build_depends_list.append(paragraphs[0][field])
        build_depends = ", ".join(build_depends_list)
        for dep1 in build_depends.split(","):
            for dep2 in dep1.split("|"):
                if m := parse_dep(dep2):
                    details = m.groupdict()
                    if details["arch"]:
                        architectures = details["arch"].split()
                    else:
                        architectures = [None]
                    for arch in architectures:
                        self.build_depends.setdefault(details["name"], {})[arch] = (
                            details["version"]
                        )

        for paragraph_no, paragraph in enumerate(paragraphs[1:], 2):
            if "package" not in paragraph:
                raise Exception(
                    "Unable to parse debian/control, paragraph %i "
                    "missing Package field" % paragraph_no
                )
            binary_package = paragraph["package"]
            if skip_tpl and binary_package.startswith(skip_tpl):
                log.debug("skipping package: %s", binary_package)
                continue
            if pkgs and binary_package not in pkgs:
                continue
            if skip_pkgs and binary_package in skip_pkgs:
                continue
            if options.remaining_packages and self.has_acted_on_package(binary_package):
                continue
            pkg = PackageData(
                substvars={},
                autoscripts={},
                rtupdates=[],
                arch=paragraph["architecture"],
            )
            if (
                options.arch is False
                and pkg.arch != "all"
                or options.arch is True
                and pkg.arch == "all"
            ):
                # TODO: check also if arch matches current architecture:
                continue

            if not binary_package.startswith(PKG_NAME_TPLS[impl]):
                # package doesn't have common prefix (python3-)
                # so lets check if Depends/Recommends contains the
                # appropriate substvar
                if substvar not in paragraph.get(
                    "depends", ""
                ) and substvar not in paragraph.get("recommends", ""):
                    log.debug(
                        "skipping package %s (missing %s in Depends/Recommends)",
                        binary_package,
                        substvar,
                    )
                    continue
            # Operate on binary_package
            self.packages[binary_package] = pkg

        fp.close()
        log.debug(
            "source=%s, binary packages=%s",
            self.source_name,
            list(self.packages.keys()),
        )

    def has_acted_on_package(self, package: str) -> bool:
        try:
            with open(f"debian/{package}.debhelper.log", encoding="utf-8") as f:
                for line in f:
                    if line.strip() == self.command:
                        return True
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        return False

    def addsubstvar(self, package: str, name: str, value: str) -> None:
        """debhelper's addsubstvar"""
        self.packages[package].substvars.setdefault(name, []).append(value)

    def autoscript(self, package: str, when: str, template: str, args: str) -> None:
        """debhelper's autoscript"""
        self.packages[package].autoscripts.setdefault(when, {}).setdefault(
            template, []
        ).append(args)

    def add_rtupdate(self, package: str, value: tuple[str, str]) -> None:
        self.packages[package].rtupdates.append(value)

    def save_autoscripts(self) -> None:
        for package, settings in self.packages.items():
            autoscripts = settings.autoscripts
            if not autoscripts:
                continue

            for when, templates in autoscripts.items():
                fn = f"debian/{package}.{when}.debhelper"
                if exists(fn):
                    with open(fn, encoding="utf-8") as datafile:
                        data = datafile.read()
                else:
                    data = ""

                new_data = ""
                for tpl_name, args in templates.items():
                    for i in args:
                        # try local one first (useful while testing dh_python3)
                        fpath = join(
                            dirname(__file__), "..", "autoscripts/%s" % tpl_name
                        )
                        if not exists(fpath):
                            fpath = "/usr/share/debhelper/autoscripts/%s" % tpl_name
                        with open(fpath, encoding="utf-8") as tplfile:
                            tpl = tplfile.read()
                        if self.options.compile_all and args:
                            # TODO: should args be checked to contain dir name?
                            tpl = tpl.replace("-p #PACKAGE#", "")
                        elif settings.arch == "all":
                            tpl = tpl.replace("#PACKAGE#", package)
                        else:
                            arch = environ["DEB_HOST_ARCH"]
                            tpl = tpl.replace("#PACKAGE#", f"{package}:{arch}")
                        tpl = tpl.replace("#ARGS#", i)
                        if tpl not in data and tpl not in new_data:
                            new_data += "\n%s" % tpl
                if new_data:
                    data += (
                        f"\n# Automatically added by {basename(argv[0])}"
                        + f"{new_data}\n# End automatically added section\n"
                    )
                    with open(fn, "w", encoding="utf-8") as fp:
                        fp.write(data)

    def save_substvars(self) -> None:
        for package, settings in self.packages.items():
            substvars = settings.substvars
            if not substvars:
                continue
            fn = "debian/%s.substvars" % package
            if exists(fn):
                with open(fn, encoding="utf-8") as datafile:
                    data = datafile.read()
            else:
                data = ""
            for name, values in substvars.items():
                p = data.find("%s=" % name)
                if p > -1:  # parse the line and remove it from data
                    e = data[p:].find("\n")
                    line = data[p + len("%s=" % name) : p + e if e > -1 else None]
                    items = [i.strip() for i in line.split(",") if i]
                    if e > -1 and data[p + e :].strip():
                        data = f"{data[:p]}\n{data[p + e :]}"
                    else:
                        data = data[:p]
                else:
                    items = []
                for j in values:
                    if j not in items:
                        items.append(j)
                if items:
                    if data:
                        data += "\n"
                    data += "{}={}\n".format(name, ", ".join(items))
            data = data.replace("\n\n", "\n")
            if data:
                with open(fn, "w", encoding="utf-8") as fp:
                    fp.write(data)

    def save_rtupdate(self) -> None:
        for package, settings in self.packages.items():
            pkg_arg = "" if self.options.compile_all else "-p %s" % package
            values = settings.rtupdates
            if not values:
                continue
            d = f"debian/{package}/{RT_LOCATIONS[self.impl]}"
            if not exists(d):
                makedirs(d)
            fn = f"{d}/{package}.rtupdate"
            if exists(fn):
                with open(fn, encoding="utf-8") as fp:
                    data = fp.read()
            else:
                data = "#! /bin/sh\nset -e"
            for dname, args in values:
                cmd = RT_TPLS[self.impl].format(pkg_arg=pkg_arg, dname=dname, args=args)
                if cmd not in data:
                    data += "\n%s" % cmd
            if data:
                with open(fn, "w", encoding="utf-8") as fp:
                    fp.write(data)
                chmod(fn, 0o755)

    def save_log(self) -> None:
        if not self.options.write_log:
            return
        for package, _ in self.packages.items():
            with open(f"debian/{package}.debhelper.log", "a", encoding="utf-8") as f:
                f.write(self.command + "\n")

    def save(self) -> None:
        self.save_substvars()
        self.save_autoscripts()
        self.save_rtupdate()
        self.save_log()
