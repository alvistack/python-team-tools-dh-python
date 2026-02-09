# Copyright © 2025 Stefano Rivera <stefanor@debian.org>
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

from argparse import ArgumentParser, Action, Namespace
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, override
from os import environ, getcwd

from dhpython.version import Version

DEFAULT_EXT_PATTERN = r"\.so(\.[^/]*)?$"
DEFAULT_INSTALL_DIR = "/usr/lib/python{version}/dist-packages"

@dataclass
class PybuildOptions:
    verbose: bool = environ.get("PYBUILD_VERBOSE") == "1"
    quiet: bool = environ.get("PYBUILD_QUIET") == "1"
    really_quiet: bool = environ.get("PYBUILD_RQUIET") == "1"
    detect_only: bool = False
    clean_only: bool = False
    configure_only: bool = False
    build_only: bool = False
    install_only: bool = False
    test_only: bool = False
    autopkgtest_only: bool = False
    list_systems: bool = False
    print_args: list[str] = field(default_factory=list)
    before_clean: str | None = None
    clean_args: str | None = None
    after_clean: str | None = None
    before_configure: str | None = None
    configure_args: str | None = None
    after_configure: str | None = None
    before_build: str | None = None
    build_args: str | None = None
    after_build: str | None = None
    before_install: str | None = None
    install_args: str | None = None
    after_install: str | None = None
    before_test: str | None = None
    test_args: str | None = None
    after_test: str | None = None
    test_nose: bool = environ.get("PYBUILD_TEST_NOSE") == "1"
    test_nose2: bool = environ.get("PYBUILD_TEST_NOSE2") == "1"
    test_pytest: bool = environ.get("PYBUILD_TEST_PYTEST") == "1"
    test_tox: bool = environ.get("PYBUILD_TEST_TOX") == "1"
    test_stestr: bool = environ.get("PYBUILD_TEST_STESTR") == "1"
    test_unittest: bool = environ.get("PYBUILD_TEST_UNITTEST") == "1"
    test_custom: bool = environ.get("PYBUILD_TEST_CUSTOM") == "1"
    dir: str = environ.get("PYBUILD_DIR", getcwd())
    # We handle this default manually, because --name affects it
    destdir: str | None = None
    ext_destdir: str | None = environ.get("PYBUILD_EXT_DESTDIR")
    ext_pattern: str = environ.get("PYBUILD_EXT_PATTERN", DEFAULT_EXT_PATTERN)
    ext_sub_pattern: str | None = environ.get("PYBUILD_EXT_SUB_PATTERN")
    ext_sub_repl: str | None = environ.get("PYBUILD_EXT_SUB_REPL")
    install_dir: str = DEFAULT_INSTALL_DIR
    name: str | None = environ.get("PYBUILD_NAME")
    system: str | None = environ.get("PYBUILD_SYSTEM")
    versions: list[Version] = field(default_factory=list)
    interpreter: list[str] = field(default_factory=list)
    disable: str | None = None
    custom_tests: bool = False


class AppendVersions(Action):
    """
    Append possibly-space-separated versions.

    This allows the use of -p "$(py3versions -rv)".
    """

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        assert isinstance(values, str)
        for value in values.split():
            getattr(namespace, self.dest).append(Version(value))


def build_parser() -> ArgumentParser:
    usage = "%(prog)s [ACTION] [BUILD SYSTEM ARGS] [DIRECTORIES] [OPTIONS]"
    parser = ArgumentParser(usage=usage)
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="turn verbose mode on",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="doesn't show external command's output",
    )
    parser.add_argument(
        "-qq",
        "--really-quiet",
        action="store_true",
        help="be quiet",
    )
    parser.add_argument("--version", action="version", version="%(prog)s DEVELV")

    action = parser.add_argument_group(
        "ACTION",
        """The default is to build,
        install and test the library using detected build system version by
        version. Selecting one of following actions, will invoke given action
        for all versions - one by one - which (contrary to the default action)
        in some build systems can overwrite previous results.""",
    )
    action.add_argument(
        "--detect",
        action="store_true",
        dest="detect_only",
        help="return the name of detected build system",
    )
    action.add_argument(
        "--clean",
        action="store_true",
        dest="clean_only",
        help="clean files using auto-detected build system specific methods",
    )
    action.add_argument(
        "--configure",
        action="store_true",
        dest="configure_only",
        help="invoke configure step for all requested Python versions",
    )
    action.add_argument(
        "--build",
        action="store_true",
        dest="build_only",
        help="invoke build step for all requested Python versions",
    )
    action.add_argument(
        "--install",
        action="store_true",
        dest="install_only",
        help="invoke install step for all requested Python versions",
    )
    action.add_argument(
        "--test",
        action="store_true",
        dest="test_only",
        help="invoke tests for auto-detected build system",
    )
    action.add_argument(
        "--autopkgtest",
        action="store_true",
        dest="autopkgtest_only",
        help="invoke autopkgtests for auto-detected build system",
    )
    action.add_argument(
        "--list-systems",
        action="store_true",
        help="list available build systems and exit",
    )
    action.add_argument(
        "--print",
        action="append",
        dest="print_args",
        help="print pybuild's internal parameters",
    )

    arguments = parser.add_argument_group(
        "BUILD SYSTEM ARGS",
        """
        Additional arguments passed to the build system.
        --system=custom requires complete command.""",
    )
    arguments.add_argument(
        "--before-clean", metavar="CMD", help="invoked before the clean command"
    )
    arguments.add_argument("--clean-args", metavar="ARGS")
    arguments.add_argument(
        "--after-clean", metavar="CMD", help="invoked after the clean command"
    )

    arguments.add_argument(
        "--before-configure", metavar="CMD", help="invoked before the configure command"
    )
    arguments.add_argument("--configure-args", metavar="ARGS")
    arguments.add_argument(
        "--after-configure", metavar="CMD", help="invoked after the configure command"
    )

    arguments.add_argument(
        "--before-build", metavar="CMD", help="invoked before the build command"
    )
    arguments.add_argument("--build-args", metavar="ARGS")
    arguments.add_argument(
        "--after-build", metavar="CMD", help="invoked after the build command"
    )

    arguments.add_argument(
        "--before-install", metavar="CMD", help="invoked before the install command"
    )
    arguments.add_argument("--install-args", metavar="ARGS")
    arguments.add_argument(
        "--after-install", metavar="CMD", help="invoked after the install command"
    )

    arguments.add_argument(
        "--before-test", metavar="CMD", help="invoked before the test command"
    )
    arguments.add_argument("--test-args", metavar="ARGS")
    arguments.add_argument(
        "--after-test", metavar="CMD", help="invoked after the test command"
    )

    tests = parser.add_argument_group(
        "TESTS",
        """\
        unittest\'s discover is used by default (if available)""",
    )
    tests.add_argument(
        "--test-nose",
        action="store_true",
        help="use nose module in --test step",
    )
    tests.add_argument(
        "--test-nose2",
        action="store_true",
        help="use nose2 module in --test step",
    )
    tests.add_argument(
        "--test-pytest",
        action="store_true",
        help="use pytest module in --test step",
    )
    tests.add_argument(
        "--test-tox",
        action="store_true",
        help="use tox in --test step",
    )
    tests.add_argument(
        "--test-stestr",
        action="store_true",
        help="use stestr in --test step",
    )
    tests.add_argument(
        "--test-unittest",
        action="store_true",
        help="use unittest in --test step",
    )
    tests.add_argument(
        "--test-custom",
        action="store_true",
        help="use custom command in --test step",
    )

    dirs = parser.add_argument_group("DIRECTORIES")
    dirs.add_argument(
        "-d",
        "--dir",
        action="store",
        metavar="DIR",
        help="source files directory - base for other relative dirs [default: CWD]",
    )
    dirs.add_argument(
        "--dest-dir",
        action="store",
        metavar="DIR",
        dest="destdir",
        help="destination directory [default: debian/tmp]",
    )
    dirs.add_argument(
        "--ext-dest-dir",
        action="store",
        metavar="DIR",
        dest="ext_destdir",
        help="destination directory for .so files",
    )
    dirs.add_argument(
        "--ext-pattern",
        action="store",
        metavar="PATTERN",
        help="regular expression for files that should be moved"
        " if --ext-dest-dir is set [default: .so files]",
    )
    dirs.add_argument(
        "--ext-sub-pattern",
        action="store",
        metavar="PATTERN",
        help="pattern to change --ext-pattern's filename or path",
    )
    dirs.add_argument(
        "--ext-sub-repl",
        action="store",
        metavar="PATTERN",
        help="replacement for match from --ext-sub-pattern," " empty string by default",
    )
    dirs.add_argument(
        "--install-dir",
        action="store",
        metavar="DIR",
        help="installation directory [default: .../dist-packages]",
    )
    dirs.add_argument(
        "--name",
        action="store",
        help="use this name to guess destination directories",
    )

    limit = parser.add_argument_group("LIMITATIONS")
    limit.add_argument(
        "-s",
        "--system",
        help="select a build system [default: auto-detection]",
    )
    limit.add_argument(
        "-p",
        "--pyver",
        action=AppendVersions,
        dest="versions",
        help="""build for Python VERSION.
                               This option can be used multiple times
                               [default: all supported Python 3.X versions]""",
    )
    limit.add_argument(
        "-i",
        "--interpreter",
        action="append",
        help="change interpreter [default: python{version}]",
    )
    limit.add_argument(
        "--disable", metavar="ITEMS", help="disable action, interpreter or version"
    )
    return parser
