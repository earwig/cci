from __future__ import annotations
import dataclasses
from dataclasses import dataclass
import json
from pathlib import Path
import textwrap
from typing import Dict, List, Optional

from colorama import Fore, Style

@dataclass
class Revision:
    raw: str

    @classmethod
    def load(cls, raw: dict) -> Revision:
        return cls(**raw)


@dataclass
class CullRule:
    name: str
    detail: Optional[str] = None

    @classmethod
    def load(cls, raw: dict) -> CullRule:
        return cls(**raw)


@dataclass
class Line:
    index: int
    raw: str
    text: str
    culled: bool = False
    rules: List[CullRule] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        maxrulelen = 32
        statuslen = maxrulelen + 16
        prefix = f'{Style.DIM}{self.index:-3d}:{Style.RESET_ALL} '
        lines = textwrap.wrap(self.text, width=200, subsequent_indent=' ' * statuslen)
        if not self.culled:
            text = '\n'.join(lines)
            return (
                f'{prefix}{Style.BRIGHT}{Fore.RED}live:{Style.RESET_ALL}     '
                f'{" " * maxrulelen} {text}'
            )
        rules = textwrap.shorten(', '.join(rule.name for rule in self.rules),
                                 maxrulelen, placeholder=' ...')
        rules = f'({rules}):'.ljust(maxrulelen + 3)
        text = '\n'.join(Style.DIM + line for line in lines)
        return (
            f'{prefix}{Style.DIM}{Fore.GREEN}culled {rules}{Fore.RESET} '
            f'{text}{Style.RESET_ALL}'
        )

    @classmethod
    def load(cls, raw: dict) -> Line:
        kwargs = raw.copy()
        kwargs['rules'] = [CullRule.load(rule) for rule in kwargs['rules']]
        return cls(**raw)


@dataclass
class Delta:
    lines: List[Line]

    @classmethod
    def load(cls, raw: dict) -> Delta:
        return cls(lines=[Line.load(line) for line in raw['lines']])


@dataclass
class Edit:
    casepage: str
    section: str
    page: str
    diff: int
    before: Revision
    after: Revision
    delta: Optional[Delta] = None

    @classmethod
    def load(cls, raw: dict) -> Edit:
        kwargs = raw.copy()
        for arg in ['before', 'after']:
            kwargs[arg] = Revision.load(kwargs[arg])
        if kwargs.get('delta'):
            kwargs['delta'] = Delta.load(kwargs['delta'])
        return cls(**kwargs)

    @property
    def culled(self):
        return self.delta and all(line.culled for line in self.delta.lines)

    def dump(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class Diff:
    revid: int
    size: str

    @classmethod
    def load(cls, raw: dict) -> Diff:
        return cls(**raw)


@dataclass
class Page:
    title: str
    diffs: List[Diff]

    @classmethod
    def load(cls, raw: dict) -> Page:
        return cls(
            title=raw['title'],
            diffs=[Diff.load(diff) for diff in raw['diffs']],
        )


@dataclass
class Section:
    title: str
    pages: List[Page]

    @classmethod
    def load(cls, raw: dict) -> Section:
        return cls(
            title=raw['title'],
            pages=[Page.load(page) for page in raw['pages']],
        )


@dataclass
class CasePage:
    index: str
    sections: Dict[str, Section]

    @classmethod
    def load(cls, index: str, raw: dict) -> CasePage:
        sections = {name: Section.load(section)
                    for name, section in raw['sections'].items()}
        return cls(index=index, sections=sections)


@dataclass
class Case:
    pages: Dict[str, CasePage]
    index: List[str] = dataclasses.field(init=False)

    def __post_init__(self):
        self.index = list(self.pages.keys())

    @classmethod
    def load(cls, case_dir: Path) -> Case:
        with (case_dir / 'index.json').open('r') as fp:
            index = json.load(fp)
        pages = {}
        for name in index:
            with (case_dir / f'{name}.json').open('r') as fp:
                pages[name] = CasePage.load(name, json.load(fp))
        return cls(pages)

    def save(self, case_dir: Path):
        with (case_dir / 'index.json').open('w') as fp:
            json.dump(self.index, fp)
        for name, page in self.pages.items():
            with (case_dir / f'{name}.json').open('w') as fp:
                json.dump(dataclasses.asdict(page), fp)
