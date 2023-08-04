#!/usr/bin/make -f
include ../common.mk

DI=debian/python3-foo/usr/lib/python3/dist-packages/foo-0.1.dist-info

check:
	test -f debian/python3-foo/usr/lib/python3/dist-packages/foo/__init__.py
	test -f debian/python3-foo/usr/bin/foo
	test ! -f $(DI)/RECORD
	test ! -f $(DI)/direct_url.json
	grep -q debian debian/python3-foo/usr/lib/python3/dist-packages/foo-0.1.dist-info/INSTALLER
	grep -q 'Depends:.*python3-cachy' debian/python3-foo/DEBIAN/control
	grep -q 'Depends:.*python3-importlib-metadata \| python3 (>> 3\.5)' debian/python3-foo/DEBIAN/control
	grep -L 'Depends:.*tox' debian/python3-foo/DEBIAN/control | grep -q control
	find .pybuild -name test-executed | grep -q test-executed
	test -f debian/python3-foo/usr/share/man/man1/foo.1.gz

clean:
	./debian/rules clean
