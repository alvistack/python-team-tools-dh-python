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

from dataclasses import asdict, dataclass, field, replace
from typing import Any
from shlex import quote

from dhpython.interpreter import Interpreter
from dhpython.version import Version


@dataclass
class Args:
    ENV: dict[str, str]
    args: str
    autopkgtest: bool
    build_dir: str
    destdir: str
    dir: str
    home_dir: str
    install_dir: str
    interpreter: Interpreter
    package: str
    version: Version
    # during tests only:
    test_dir: str | None = None
    # Injected by base:
    ignore_no_tests: bool = False
    wheel: str | None = None
    # Injected by plugin_distutils:
    setup_py: str | None = None

    def format(self, template: str) -> str:
        return template.format(**self.as_dict())

    def format_quoted(self, template: str) -> str:
        quoted = self.as_dict()
        for k, v in quoted.items():
            if v and (k in ('dir', 'destdir') or k.endswith('_dir')):
                assert isinstance(v, str)
                quoted[k] = quote(v)
        return template.format(**quoted)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Context:
    ENV: dict[str, str]
    dir: str
    destdir: str
    args: dict[str, str] = field(default_factory=dict)

    def copy(self) -> "Context":
        return replace(self)
