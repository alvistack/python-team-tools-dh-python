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
from collections.abc import Callable
from functools import wraps
from glob import glob1
from os import environ, remove, walk, makedirs
from os.path import exists, isdir, join
from pathlib import Path
from shutil import rmtree, copyfile, copytree, which
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Concatenate,
    Literal,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

from dhpython.debhelper import DebHelper, build_options
from dhpython.exceptions import RequiredCommandMissingException
from dhpython.tools import execute, ExecutionResult, ExecutionResultWithOutput
from dhpython.build.options import PybuildOptions
from dhpython.build.types import Args, Context

if TYPE_CHECKING:
    from functools import _Wrapped

log = logging.getLogger('dhpython')

P = ParamSpec('P')
T = TypeVar('T')
BC = TypeVar('BC', bound="Base")

def copy_test_files(
    dest: str = '{build_dir}',
    filelist: str = '{home_dir}/testfiles_to_rm_before_install',
    add_to_args: tuple[str, ...] = ('test', 'tests')
) -> Callable[
        [Callable[Concatenate[BC, Context, Args, P], T]],
        Callable[Concatenate[BC, Context, Args, P], T],
    ]:

    def _copy_test_files(
        func: Callable[Concatenate[BC, Context, Args, P], T], /
    ) -> "_Wrapped[Concatenate[BC, Context, Args, P], T, Concatenate[BC, Context, Args, P], T]":

        @wraps(func)
        def __copy_test_files(
            self: BC,
            context: Context,
            args: Args,
            *oargs: P.args,
            **kwargs: P.kwargs
        ) -> T:
            files_to_copy = {'pyproject.toml', 'pytest.ini', 'test', 'tests'}
            # check debian/pybuild_pythonX.Y.testfiles
            for tpl in ('_{i}{v}', '_{i}{m}', ''):
                tpl = tpl.format(i=args.interpreter.name,
                                 v=args.version,
                                 m=args.version.major)
                fpath = join(args.dir, f'debian/pybuild{tpl}.testfiles')
                if exists(fpath):
                    with open(fpath, encoding='utf-8') as fp:
                        # overwrite files_to_copy if .testfiles file found
                        files_to_copy = set()
                        for line in fp.readlines():
                            line = line.strip()
                            if line.startswith('#'):
                                continue
                            if not line:
                                continue
                            files_to_copy.add(line)
                        break

            files_to_remove = set()
            for entry in files_to_copy:
                name, *rest = entry.split(maxsplit=1)
                dest_suffix = rest[0] if rest else ""
                if not dest_suffix or dest_suffix.endswith('/'):
                    dest_suffix = join(dest_suffix, name.rsplit('/', 1)[-1])

                src_dpath = join(args.dir, name)
                dst_dpath = join(args.format(dest), dest_suffix)
                if exists(src_dpath):
                    if not exists(dst_dpath):
                        log.debug("Copying %s to %s for tests", src_dpath, dst_dpath)
                        makedirs(dst_dpath.rsplit('/', 1)[0], exist_ok=True)
                        if isdir(src_dpath):
                            copytree(src_dpath, dst_dpath)
                        else:
                            copyfile(src_dpath, dst_dpath)
                        files_to_remove.add(dst_dpath + '\n')
                    if not args.args and 'PYBUILD_TEST_ARGS' not in context.ENV\
                       and (self.cfg.test_pytest or self.cfg.test_nose) \
                       and name in add_to_args:
                        args.args = name
            if files_to_remove and filelist:
                with open(args.format(filelist), 'a', encoding="UTF-8") as fp:
                    fp.writelines(files_to_remove)

            return func(self, context, args, *oargs, **kwargs)
        return __copy_test_files
    return _copy_test_files


class Base:
    """Base class for build system plugins

    :attr REQUIRED_COMMANDS: list of command checked by default in :meth:is_usable,
        if one of them is missing, plugin cannot be used.
    :type REQUIRED_COMMANDS: list of strings
    :attr REQUIRED_FILES: list of files (or glob templates) required by given
        build system
    :attr OPTIONAL_FILES: dictionary of glob templates (key) and score (value)
        used to detect if given plugin is the best one for the job
    :type OPTIONAL_FILES: dict (key is a string, value is an int)
    :attr SUPPORTED_INTERPRETERS: set of interpreter templates (with or without
        {version}) supported by given plugin
    """
    cfg: PybuildOptions
    NAME: ClassVar[str]
    DESCRIPTION = ''
    REQUIRED_COMMANDS: list[str] = []
    REQUIRED_FILES: list[str] = []
    DETECTED_REQUIRED_FILES: dict[str, list[str]]
    OPTIONAL_FILES: dict[str, int] = {}
    DETECTED_OPTIONAL_FILES: dict[str, list[str]]
    SUPPORTED_INTERPRETERS: Literal[True] | set[str] = {
        'python', 'python3', 'python-dbg', 'python3-dbg',
        'python{version}', 'python{version}-dbg'
    }
    # files and directories to remove during clean step (other than .pyc):
    CLEAN_FILES = {'.pytest_cache', '.coverage'}

    def __init__(self, cfg: PybuildOptions) -> None:
        self.cfg = cfg

    def __repr__(self) -> str:
        return "BuildSystem(%s)" % self.NAME

    @classmethod
    def is_usable(cls) -> None:
        for command in cls.REQUIRED_COMMANDS:
            pth = which(command)
            if not pth:
                raise RequiredCommandMissingException(command)

    def detect(self, context: Context) -> int:
        """Return certainty level that this plugin describes the right build system

        This method is using cls.{REQUIRED,OPTIONAL}_FILES only by default,
        please extend it in the plugin if more sofisticated methods can be used
        for given build system.

        :return: 0 <= certainty <= 100
        :rtype: int
        """
        result = 0

        required_files_num = 0
        self.DETECTED_REQUIRED_FILES = {}  # can be used in the plugin later
        for tpl in self.REQUIRED_FILES:
            found = False
            for ftpl in tpl.split('|'):
                res = glob1(context.dir, ftpl)
                if res:
                    found = True
                    self.DETECTED_REQUIRED_FILES.setdefault(tpl, []).extend(res)
            if found:
                required_files_num += 1
        # add max 50 points depending on how many required files are available
        if self.REQUIRED_FILES:
            result += int(required_files_num / len(self.REQUIRED_FILES) * 50)

        self.DETECTED_OPTIONAL_FILES = {}
        for ftpl, score in self.OPTIONAL_FILES.items():
            res = glob1(context.dir, ftpl)
            if res:
                result += score
                self.DETECTED_OPTIONAL_FILES.setdefault(ftpl, []).extend(res)
        if result > 100:
            return 100
        return result

    def clean(self, context: Context, args: Args) -> None:
        tox_dir = join(args.dir, '.tox')
        if isdir(tox_dir):
            try:
                rmtree(tox_dir)
            except Exception:
                log.debug('cannot remove %s', tox_dir)

        for fn in self.CLEAN_FILES:
            path = join(context.dir, fn)
            if isdir(path):
                try:
                    rmtree(path)
                except Exception:
                    log.debug('cannot remove %s', path)
            elif exists(path):
                try:
                    remove(path)
                except Exception:
                    log.debug('cannot remove %s', path)

        dh = DebHelper(build_options())
        # Plugins that rely on repository contents to build MANIFEST
        clean_sources_txt = not {
            'python3-setuptools-scm', 'python3-setuptools-git'
        }.intersection(set(dh.build_depends))

        for root, dirs, file_names in walk(context.dir):
            for name in dirs[:]:
                if name == '__pycache__' or (
                        clean_sources_txt and name.endswith('.egg-info')):
                    dpath = join(root, name)
                    log.debug('removing dir: %s', dpath)
                    try:
                        rmtree(dpath)
                    except Exception:
                        log.debug('cannot remove %s', dpath)
                    else:
                        dirs.remove(name)
            for fn in file_names:
                if fn.endswith(('.pyc', '.pyo')):
                    fpath = join(root, fn)
                    log.debug('removing: %s', fpath)
                    try:
                        remove(fpath)
                    except Exception:
                        log.debug('cannot remove %s', fpath)
            if root.endswith('.egg-info'):
                for fn in file_names:
                    if fn != 'SOURCES.txt':
                        fpath = join(root, fn)
                        log.debug('removing: %s', fpath)
                        try:
                            remove(fpath)
                        except Exception:
                            log.debug('cannot remove %s', fpath)

    def configure(self, context: Context, args: Args) -> None:
        raise NotImplementedError("configure method not implemented in %s" % self.NAME)

    def install(self, context: Context, args: Args) -> None:
        raise NotImplementedError("install method not implemented in %s" % self.NAME)

    def build(self, context: Context, args: Args) -> None:
        raise NotImplementedError("build method not implemented in %s" % self.NAME)

    def test(self, context: Context, args: Args) -> None:
        raise NotImplementedError("test method not implemented in %s" % self.NAME)

    @copy_test_files()
    def test_cmd(self, context: Context, args: Args) -> str:
        if self.cfg.test_nose2:
            return 'cd {build_dir}; {interpreter} -m nose2 -v {args}'
        elif self.cfg.test_nose:
            return 'cd {build_dir}; {interpreter} -m nose -v {args}'
        elif self.cfg.test_pytest:
            return 'cd {build_dir}; {interpreter} -m pytest {args}'
        elif self.cfg.test_tox:
            tox_config = None
            if exists(join(args.dir, 'tox.ini')):
                tox_config = '{dir}/tox.ini'
            elif exists(join(args.dir, 'pyproject.toml')):
                tox_config = '{dir}/pyproject.toml'
            elif exists(join(args.dir, 'setup.cfg')):
                tox_config = '{dir}/setup.cfg'
            else:
                raise Exception("tox config not found. "
                    "Expected to find tox.ini, pyproject.toml, or setup.cfg")

            tox_cmd = ['cd {build_dir};',
                   'tox',
                   '-c', tox_config,
                   '--sitepackages',
                   '-e', 'py{version.major}{version.minor}',
                   '-x', 'testenv.passenv+=_PYTHON_HOST_PLATFORM',
            ]
            if args.autopkgtest:
                tox_cmd += ['--skip-pkg-install']

            if not args.autopkgtest:
                wheel = self.built_wheel(context, args)
                if not wheel:
                    self.build_wheel(context, args)
                    wheel = self.built_wheel(context, args)
                assert wheel
                args.wheel = wheel
                tox_cmd += ['--installpkg', '{wheel}']

            tox_cmd.append('{args}')
            return ' '.join(tox_cmd)
        elif self.cfg.test_stestr:
            return (
                'cd {build_dir};'
                'stestr --config {dir}/.stestr.conf init;'
                'PYTHON=python{version} stestr --config {dir}/.stestr.conf run'
            )
        elif self.cfg.test_unittest:
            return 'cd {build_dir}; {interpreter} -m unittest discover -v {args}'
        elif self.cfg.test_custom:
            return 'cd {build_dir}; {args}'
        else:
            log.warning(
                "No test runner selected, defaulting to unittest, ignoring "
                "test discovery problems.\nUse --test-unittest to explicitly "
                "select the unittest runner.")
            # As this is the fallback option, we allow 0 discovered tests.
            args.ignore_no_tests = True
            return 'cd {build_dir}; {interpreter} -m unittest discover -v {args}'

    def build_wheel(self, context: Context, args: Args) -> None:
        raise NotImplementedError("build_wheel method not implemented in %s" % self.NAME)

    def built_wheel(self, context: Context, args: Args) -> str | None:
        """Return the path to any built wheels we can find"""
        # pylint: disable=unused-argument
        wheels = list(Path(args.home_dir).glob('*.whl'))
        n_wheels = len(wheels)
        if n_wheels > 1:
            raise Exception(f"Expecting to have built exactly 1 wheel, but found {n_wheels}")
        if n_wheels == 1:
            return str(wheels[0])
        return None

    @overload
    def execute(
        self,
        context: Context,
        args: Args,
        command: str,
        *,
        log_file: None = None,
    ) -> ExecutionResultWithOutput:
        ...

    @overload
    def execute(
        self,
        context: Context,
        args: Args,
        command: str,
        *,
        log_file: str | Literal[False],
    ) -> ExecutionResult:
        ...

    def execute(
        self,
        context: Context,
        args: Args,
        command: str,
        *,
        log_file: str | Literal[False] | None = None
    ) -> ExecutionResult | ExecutionResultWithOutput:
        if log_file is False and self.cfg.really_quiet:
            log_file = None
        command = args.format(command)
        env = dict(context.ENV)
        env.update(args.ENV)
        log.info(command)
        return execute(command, cwd=context.dir, env=env, log_output=log_file)

    def print_args(self, context: Context, args: Args) -> None:
        # pylint: disable=unused-argument
        cfg = self.cfg
        if len(cfg.print_args) == 1 and len(cfg.interpreter) == 1 and '{version}' not in cfg.interpreter[0]:
            i = cfg.print_args[0]
            if '{' in i:
                print(args.format(i))
            else:
                print(args.as_dict().get(i, ''))
        else:
            for i in cfg.print_args:
                if '{' in i:
                    print(args.format(i))
                else:
                    print('{} {}: {}'.format(args.interpreter, i, args.as_dict().get(i, '')))


def shell_command(
    func: Callable[Concatenate[BC, Context, Args, P], str | Literal[0]], /
) -> Callable[Concatenate[BC, Context, Args, P], None]:

    @wraps(func)
    def wrapped_func(
        self: BC,
        context: Context,
        args: Args,
        *oargs: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        command = kwargs.pop('command', None)
        if not command:
            command = func(self, context, args, *oargs, **kwargs)
            if isinstance(command, int):  # final result
                return
        assert isinstance(command, str)
        if not command:
            log.warning('missing command '
                     '(plugin=%s, method=%s, interpreter=%s, version=%s)',
                     self.NAME, func.__name__,
                     args.interpreter, args.version)
            return

        log_file: str | Literal[False]
        if self.cfg.quiet:
            log_file = join(args.home_dir, f'{func.__name__}_cmd.log')
        else:
            log_file = False

        command = args.format_quoted(command)

        output = self.execute(context, args, command=command, log_file=log_file)
        if output.returncode == 5 and args.ignore_no_tests:
            # Temporary hack (see Base.test)
            pass
        elif output.returncode != 0:
            msg = f'exit code={output.returncode}: {command}'
            if log_file:
                msg += f'\nfull command log is available in {log_file}'
            raise Exception(msg)

    # Workaround https://github.com/python/typeshed/issues/10653
    return cast(Callable[Concatenate[BC, Context, Args, P], None], wrapped_func)


def get_parallel() -> int:
    """Determine the allowable level of build parallelism with DEB_BUILD_OPTIONS."""
    parallel = 1
    if 'DEB_BUILD_OPTIONS' in environ:
        for option in environ['DEB_BUILD_OPTIONS'].split():
            key, assign, value = option.partition('=')
            if key == "parallel" and assign == "=":
                parallel = int(value)
    return parallel


def create_setuptools_parallel_cfg(
    backend: str | None = None
) -> Callable[
        [Callable[Concatenate[BC, Context, Args, P], T]],
        Callable[Concatenate[BC, Context, Args, P], T],
]:
    """Enable parallel building of extensions, respecting DEB_BUILD_OPTIONS.

    An adaption of Michał Górny's technique described in
    https://blogs.gentoo.org/mgorny/2024/03/15/optimizing-parallel-extension-builds-in-pep517-builds

    This function is not part of :pyfunc:`create_pydistutils_cfg` as that
    function is not used for `build_wheel`, which is our target.

    For PEP-517 (pyproject) builds we can not yet use PEP-517 Config Settings
    as we need to pass the parallel building option to `build_ext` and
    setuptools (as of version 80.9.0) does not have a way to redirect PEP-517
    Config Settings to specific commands. Setuptools only passes PEP-517 Config
    Settings to all commands via `--global-option` and to `build_wheel` with
    `--build-option`.
    See https://github.com/pypa/setuptools/blob/d198e86f57231e83de87975c5c82bc40c196da79/setuptools/build_meta.py
    and https://github.com/pypa/setuptools/discussions/4083
    """
    def decorator(
        func: Callable[Concatenate[BC, Context, Args, P], T], /
    ) -> Callable[Concatenate[BC, Context, Args, P], T]:
        @wraps(func)
        def wrapped_func(
            self: BC,
            context: Context,
            args: Args,
            *oargs: P.args,
            **kwargs: P.kwargs,
        ) -> T:
            fpath = join(args.home_dir, 'setuptools-build_ext-parallel.cfg')
            if not exists(fpath):
                with open(fpath, 'w', encoding='utf-8') as fp:
                    lines = ['[build_ext]\n',
                             f'parallel={get_parallel()}\n']
                    log.debug('parallel build extension config file:\n%s', ''.join(lines))
                    fp.writelines(lines)
            context.ENV['DIST_EXTRA_CONFIG'] = fpath
            return func(self, context, args, *oargs, **kwargs)

        if 'DIST_EXTRA_CONFIG' in environ or (
                backend is not None and backend != "setuptools.build_meta"):
            return func
        return cast(Callable[Concatenate[BC, Context, Args, P], T], wrapped_func)
    return decorator
