#!/usr/bin/make -f
include ../common.mk

check:
	# FIXME: This used to be a 2.7 + 3.x test. It may not be useful any more, without 2.x
	test -f debian/python3-foo/usr/lib/python3/dist-packages/foo.py
	grep -q 'Depends:.*python3-pkg-resources' debian/python3-foo/DEBIAN/control
	./debian/rules clean
	test -f foo.egg-info/SOURCES.txt
	grep -q extra-file foo.egg-info/SOURCES.txt
	test ! -f foo.egg-info/PKG-INFO
	test ! -f foo.egg-info/dependency_links.txt
	test ! -f foo.egg-info/requires.txt
	test ! -f foo.egg-info/top_level.txt

clean:
	./debian/rules clean
