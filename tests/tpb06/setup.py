from setuptools import setup, Extension

setup_args = dict(
    ext_modules=[
        Extension(
            'foo.ext',
            ['foo/ext.c'],
            depends=['foo/ext.h'],
            py_limited_api=True,
        )
    ],
    headers=['foo/ext.h'],
)
setup(**setup_args)
