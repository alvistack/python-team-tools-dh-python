#! /usr/bin/python3
# Copyright © 2013 Piotr Ożarowski <piotr@debian.org>
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
from configparser import ConfigParser
from os import environ
from os.path import exists
from subprocess import Popen, PIPE

SUPPORTED = {
    'cpython3': [(3, 8)],
}
DEFAULT = {
    'cpython3': (3, 8),
}

log = logging.getLogger('dhpython')


def cpython_versions(major):
    result = [None, None]
    assert major > 2
    ver = str(major)
    supported = environ.get("DEBPYTHON{}_SUPPORTED".format(ver))
    default = environ.get("DEBPYTHON{}_DEFAULT".format(ver))
    if not supported or not default:
        config = ConfigParser()
        config.read("/usr/share/python{}/debian_defaults".format(ver))
        if not default:
            default = config.get('DEFAULT', 'default-version', fallback='')[6:]
        if not supported:
            supported = config.get('DEFAULT', 'supported-versions', fallback='')\
                .replace('python', '')
    if default:
        try:
            result[0] = tuple(int(i) for i in default.split('.'))
        except Exception as err:
            log.warning('invalid debian_defaults file: %s', err)
    if supported:
        try:
            result[1] = tuple(tuple(int(j) for j in i.strip().split('.'))
                              for i in supported.split(','))
        except Exception as err:
            log.warning('invalid debian_defaults file: %s', err)
    return result


def from_file(fpath):
    if not exists(fpath):
        raise ValueError("missing interpreter: %s" % fpath)
    command = "{} --version".format(fpath)
    with Popen(command, shell=True, stdout=PIPE) as process:
        stdout, _ = process.communicate()
        stdout = str(stdout, 'utf-8')

    print(stdout)


cpython3 = cpython_versions(3)
if cpython3[0]:
    DEFAULT['cpython3'] = cpython3[0]
if cpython3[1]:
    SUPPORTED['cpython3'] = cpython3[1]


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print('invalid number of arguments', file=sys.stderr)
        sys.exit(1)
    if sys.argv[1] == 'default':
        print('.'.join(str(i) for i in DEFAULT[sys.argv[2]]))
    elif sys.argv[1] == 'supported':
        print(','.join(('.'.join(str(i) for i in v) for v in SUPPORTED[sys.argv[2]])))
