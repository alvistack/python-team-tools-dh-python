# Copyright © 2023 Stefano Rivera <stefanor@debian.org>
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

from os.path import join
from typing import override

from dhpython.build.base import Base, shell_command, copy_test_files
from dhpython.build.types import Args, Context


class BuildSystem(Base):
    DESCRIPTION = 'meson build system (using dh_auto_* commands)'
    REQUIRED_COMMANDS = ['meson']
    REQUIRED_FILES = ['meson.build']

    @shell_command
    @override
    def clean(self, context: Context, args: Args) -> str:
        super().clean(context, args)
        return 'dh_auto_clean --buildsystem=cmake'

    @shell_command
    @override
    def configure(self, context: Context, args: Args) -> str:
        # Can't be specified on the command line, directly
        # https://github.com/mesonbuild/meson/issues/9671
        with open(join(args.build_dir, 'pybuild-meson-native.ini'), 'w', encoding="UTF-8") as f:
            f.write('[binaries]\n')
            f.write(f"python3 = '{args.interpreter.binary_dv}'\n")

        return ('dh_auto_configure --buildsystem=meson'
                ' --builddirectory={build_dir} --'
                ' --native-file={build_dir}/pybuild-meson-native.ini'
                ' {args}')

    @shell_command
    @override
    def build(self, context: Context, args: Args) -> str:
        return ('dh_auto_build --buildsystem=meson'
                ' --builddirectory={build_dir}'
                ' -- {args}')

    @shell_command
    @override
    def install(self, context: Context, args: Args) -> str:
        return ('dh_auto_install --buildsystem=meson'
                ' --builddirectory={build_dir}'
                ' --destdir={destdir}'
                ' -- {args}')

    @copy_test_files()
    @shell_command
    @override
    def test(self, context: Context, args: Args) -> str:
        return ('dh_auto_test --buildsystem=meson'
                ' --builddirectory={build_dir}'
                ' -- {args}')
