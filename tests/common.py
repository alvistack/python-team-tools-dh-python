from typing import Any

from dhpython.version import VersionRange


class FakeOptions:
    accept_upstream_versions: bool = False
    depends: list[str]
    depends_section: list[str]
    guess_deps: bool = True
    no_ext_rename: bool = False
    recommends: list[str]
    recommends_section: list[str]
    remaining_packages: bool = False
    requires: list[str]
    suggests: list[str]
    suggests_section: list[str]
    vrange: VersionRange | None = None

    def __init__(self, **kwargs: Any) -> None:
        opts = {
            'depends': (),
            'depends_section': (),
            'guess_deps': False,
            'no_ext_rename': False,
            'recommends': (),
            'recommends_section': (),
            'requires': (),
            'suggests': (),
            'suggests_section': (),
            'vrange': None,
            'accept_upstream_versions': False,
        }
        opts.update(kwargs)
        for k, v in opts.items():
            setattr(self, k, v)
