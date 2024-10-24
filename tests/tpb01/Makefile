#!/usr/bin/make -f
include ../common.mk

check:
	test -f debian/python3-foo/usr/lib/python3/dist-packages/foo.py
	grep -q 'Depends:.*python3-cachy' debian/python3-foo/DEBIAN/control
	test -e foo.egg-info/
	./debian/rules clean
	test ! -e foo.egg-info/

clean:
	./debian/rules clean
