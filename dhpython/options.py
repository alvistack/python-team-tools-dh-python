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

import re
from argparse import ArgumentParser, SUPPRESS
from dataclasses import dataclass, field
from os import environ

from dhpython.version import VersionRange


@dataclass
class DHPythonOptions:
    O: list[str] = field(default_factory=list)
    accept_upstream_versions: bool = False
    arch: bool | None = None
    clean_dbg_pkg: bool = True
    compile_all: bool = False
    depends: list[str] = field(default_factory=list)
    depends_section: list[str] = field(default_factory=list)
    guess_deps: bool = True
    ignore_shebangs: bool = False
    no_ext_rename: bool = False
    no_package: list[str] = field(default_factory=list)
    no_shebang_rewrite: bool = False
    package: list[str] = field(default_factory=list)
    private_dir: str | None = None
    recommends: list[str] = field(default_factory=list)
    recommends_section: list[str] = field(default_factory=list)
    regexpr: list[re.Pattern[str]] = field(default_factory=list)
    remaining_packages: bool = False
    requires: list[str] = field(default_factory=list)
    shebang: str | None = None
    skip_private: bool = False
    suggests: list[str] = field(default_factory=list)
    suggests_section: list[str] = field(default_factory=list)
    verbose: bool = environ.get("DH_VERBOSE") == "1"
    vrange: VersionRange | None = None
    write_log: bool = False


def compiled_regex(string: str) -> re.Pattern[str]:
    """argparse regex type"""
    try:
        return re.compile(string)
    except re.error:
        raise ValueError("regular expression is not valid")


def build_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument("--version", action="version", version="%(prog)s DEVELV")
    parser.add_argument(
        "--no-guessing-deps",
        action="store_false",
        dest="guess_deps",
        help="disable guessing dependencies",
    )
    parser.add_argument(
        "--skip-private", action="store_true", help="don't check private directories"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="turn verbose mode on",
    )
    # arch=False->arch:all only, arch=True->arch:any only, None->all of them
    parser.add_argument(
        "-i",
        "--indep",
        action="store_false",
        dest="arch",
        default=None,
        help="act on architecture independent packages",
    )
    parser.add_argument(
        "-a",
        "-s",
        "--arch",
        action="store_true",
        dest="arch",
        help="act on architecture dependent packages",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_false", dest="verbose", help="be quiet"
    )
    parser.add_argument(
        "-p",
        "--package",
        action="append",
        metavar="PACKAGE",
        help="act on the package named PACKAGE",
    )
    parser.add_argument(
        "-N",
        "--no-package",
        action="append",
        metavar="PACKAGE",
        help="do not act on the specified package",
    )
    parser.add_argument(
        "--remaining-packages",
        action="store_true",
        help="Do not act on the packages which have already been acted on by "
        "this debhelper command earlier",
    )
    parser.add_argument(
        "--compile-all",
        action="store_true",
        help="compile all files from given private directory in postinst, not "
        "just the ones provided by the package",
    )
    parser.add_argument(
        "-V",
        type=VersionRange,
        dest="vrange",
        metavar="[X.Y][-][A.B]",
        help="specify list of supported Python versions. See py3compile(1) for "
        "examples",
    )
    parser.add_argument(
        "-X",
        "--exclude",
        action="append",
        dest="regexpr",
        type=compiled_regex,
        metavar="REGEXPR",
        help="exclude .py files that match given REGEXPR from "
        "byte-compilation, in a private dir. You may use this option "
        "multiple times to build up a list of things to exclude.",
    )
    parser.add_argument(
        "--accept-upstream-versions",
        action="store_true",
        help="accept upstream versions while translating Python dependencies "
        "into Debian ones",
    )
    parser.add_argument(
        "--depends",
        action="append",
        metavar="REQ",
        help="translate given requirements into Debian dependencies and add "
        "them to ${python3:Depends}. Use it for missing items in "
        "requires.txt.",
    )
    parser.add_argument(
        "--depends-section",
        action="append",
        metavar="SECTION",
        help="translate requirements from given section into Debian "
        "dependencies and add them to ${python3:Depends}",
    )
    parser.add_argument(
        "--recommends",
        action="append",
        metavar="REQ",
        help="translate given requirements into Debian dependencies and add "
        "them to ${python3:Recommends}",
    )
    parser.add_argument(
        "--recommends-section",
        action="append",
        metavar="SECTION",
        help="translate requirements from given section into Debian "
        "dependencies and add them to ${python3:Recommends}",
    )
    parser.add_argument(
        "--suggests",
        action="append",
        metavar="REQ",
        help="translate given requirements into Debian dependencies and add "
        "them to ${python3:Suggests}",
    )
    parser.add_argument(
        "--suggests-section",
        action="append",
        metavar="SECTION",
        help="translate requirements from given section into Debian "
        "dependencies and add them to ${python3:Suggests}",
    )
    parser.add_argument(
        "--requires",
        action="append",
        metavar="FILE",
        help="translate requirements from given file into Debian dependencies "
        "and add them to ${python3:Depends}",
    )
    parser.add_argument(
        "--shebang", metavar="COMMAND", help="use given command as shebang in scripts"
    )
    parser.add_argument(
        "--ignore-shebangs",
        action="store_true",
        help="do not translate shebangs into Debian dependencies",
    )
    parser.add_argument(
        "--no-dbg-cleaning",
        action="store_false",
        dest="clean_dbg_pkg",
        help="do not remove files from debug packages",
    )
    parser.add_argument(
        "--no-ext-rename",
        action="store_true",
        help="do not add magic tags nor multiarch tuples to extension file " "names)",
    )
    parser.add_argument(
        "--no-shebang-rewrite", action="store_true", help="do not rewrite shebangs"
    )
    parser.add_argument(
        "private_dir",
        nargs="?",
        help="Private directory containing Python modules (optional)",
    )
    # debhelper options:
    parser.add_argument("-O", action="append", help=SUPPRESS)
    return parser
