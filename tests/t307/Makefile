#!/usr/bin/make -f
include ../common.mk

all: run check

run: clean
	dpkg-buildpackage -b -us -uc

check:
	grep -qEe "^Depends: (.* )?python3-cachy($|,| )" \
		debian/python3-foo/DEBIAN/control

clean:
	./debian/rules clean
	rm -rf lib/Foo.egg-info build
