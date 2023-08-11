all: run check

run:
	@echo No build needed
ifeq ($(AUTOPKGTEST_TMP),)
	@echo NOTE this test uses the system pybuild-autopkgtest, not the working directory
endif

check:
	DH_VERBOSE=1 pybuild-autopkgtest
	test -e test-ran
	# Assert that we didn't build anything
	test ! -e .pybuild
	test ! -e build
	test ! -e dist

clean:
	./debian/rules clean
ifneq ($(AUTOPKGTEST_TMP),)
	rm -r $(AUTOPKGTEST_TMP)/*
endif
