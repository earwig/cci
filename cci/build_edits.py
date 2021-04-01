#!/usr/bin/env python3

import argparse
import functools
import gzip
import json
from pathlib import Path

import tqdm

from . import utils
from .case import Case, Edit, Revision

def build_edits(case: Case, rev_dir: Path, edits_path: Path):
    edits = []

    all_diffs = [
        (casepage, section, page, diff)
        for casepage in case.pages.values()
        for section in casepage.sections.values()
        for page in section.pages
        for diff in page.diffs
    ]
    for (casepage, section, page, diff) in tqdm.tqdm(all_diffs, unit='diffs'):
        rev = _load_rev(rev_dir, diff.revid)
        if 'missing' in rev:
            continue
        if rev['parentid'] == 0:
            prev = {'content': ''}
        else:
            prev = _load_rev(rev_dir, rev['parentid'])
            if 'missing' in prev:
                continue
            assert rev['title'] == prev['title']

        edits.append(Edit(
            casepage=casepage.index,
            section=section.title,
            page=page.title,
            diff=diff.revid,
            before=Revision(prev['content']),
            after=Revision(rev['content']),
        ))

    with gzip.open(edits_path, 'wt') as fp:
        json.dump([edit.dump() for edit in edits], fp)

@functools.cache
def _load_rev(rev_dir: Path, revid: int):
    path = rev_dir / f'{revid}.json.gz'
    with gzip.open(path, 'rt') as fp:
        return json.load(fp)

def main():
    parser = argparse.ArgumentParser(description='Build edits for CCI')
    parser.add_argument('case', help='Case dir')
    args = parser.parse_args()
    utils.setup_logging()

    root = Path(args.case)
    case = Case.load(root / 'case')
    build_edits(case, root / 'revs', root / 'edits.json.gz')

if __name__ == '__main__':
    main()
