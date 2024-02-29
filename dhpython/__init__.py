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

PKG_PREFIX_MAP = {'cpython3': 'python3'}

# minimum version required for compile/clean scripts:
MINPYCDEP = {'cpython3': 'python3:any'}

PUBLIC_DIR_RE = {
    'cpython3': re.compile(r'.*?/usr/lib/python(3(?:\.\d+)?)(?:/|$)'),
}

INTERPRETER_DIR_TPLS = {
    'cpython3': r'.*/python3(?:\.\d+)?/',
}

MULTIARCH_DIR_TPL = re.compile(
    '.*/([a-z][^/-]+-(?:linux|kfreebsd|gnu)(?:-[^/-]+)?)(?:/.*|$)')

# Interpreter site-directories
OLD_SITE_DIRS = {
    'cpython3': [
        '/usr/local/lib/python{}/site-packages',
        '/usr/local/lib/python{}/dist-packages',
        '/usr/lib/python{}/site-packages',
        '/usr/lib/python{}/dist-packages',
        '/var/lib/python-support/python{}',
        '/usr/lib/pymodules/python{}'],
}

# PyDist related
PYDIST_DIRS = {
    'cpython3': '/usr/share/python3/dist/',
}

PYDIST_OVERRIDES_FNAMES = {
    'cpython3': 'debian/py3dist-overrides',
}

PYDIST_DPKG_SEARCH_TPLS = {
    # implementation: (dpkg -S query, regex filter)
    'cpython3': ('*python3/*/{}-?*.*-info', r'.(egg|dist)-info$'),
}

# DebHelper related
DEPENDS_SUBSTVARS = {
    'cpython3': '${python3:Depends}',
}
PKG_NAME_TPLS = {
    'cpython3': ('python3-', 'python3.'),
}
RT_LOCATIONS = {
    'cpython3': '/usr/share/python3/runtime.d/',
}
RT_TPLS = {
    'cpython3': '''
if [ "$1" = rtupdate ]; then
\tpy3clean {pkg_arg} {dname}
\tpy3compile {pkg_arg} {args} {dname}
fi''',
}
