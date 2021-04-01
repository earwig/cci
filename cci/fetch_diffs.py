#!/usr/bin/env python3

import argparse
import gzip
import json
import logging
from pathlib import Path

import tqdm

from . import site, utils
from .case import Case

def fetch_diffs(case_dir: Path, rev_dir: Path):
    case = Case.load(case_dir)

    logging.info('fetching case diffs...')
    revids = [
        (page.title, diff.revid)
        for casepage in case.pages.values()
        for section in casepage.sections.values()
        for page in section.pages
        for diff in page.diffs
    ]

    for title, revid in tqdm.tqdm(revids, unit='revs'):
        path = rev_dir / f'{revid}.json.gz'
        if path.exists():
            continue

        for revid, content in _fetch_diff(title, revid).items():
            path = rev_dir / f'{revid}.json.gz'
            if path.exists():
                continue
            with gzip.open(path, 'wt') as fp:
                fp.write(json.dumps(content))

def _fetch_diff(title: str, revid: int) -> dict:
    gen = site.query(
        titles=[title],
        prop='revisions',
        rvprop='content|ids',
        rvstartid=revid,
        rvlimit=2,
        rvslots='main',
        redirects=1,
    )
    page = next(gen).pages[0]
    if 'missing' in page:
        return {revid: {'title': page.title, 'missing': 'page'}}
    if 'revisions' not in page:
        return {revid: {'title': page.title, 'missing': 'rev'}}
    revs = page.revisions
    if revs[0].revid != revid:
        return {revid: {'title': page.title, 'missing': 'rev'}}

    assert revs[0].parentid == 0 or len(revs) == 2, revid
    return {rev.revid: _format_rev(page, rev) for rev in revs}

def _format_rev(page, rev) -> dict:
    result = {
        'title': page.title,
        'parentid': rev.parentid,
    }
    if 'texthidden' in rev.slots.main:
        result['missing'] = 'content'
    else:
        result['content'] = rev.slots.main.content
    return result

def main():
    parser = argparse.ArgumentParser(description='Fetch diffs for CCI')
    parser.add_argument('case', help='Case dir')
    args = parser.parse_args()
    utils.setup_logging()

    root = Path(args.case)
    case_dir = root / 'case'
    rev_dir = root / 'revs'
    if not case_dir.exists():
        raise RuntimeError(f'Case dir {case_dir} does not exist; please run fetch_cci first')
    rev_dir.mkdir(exist_ok=True)

    fetch_diffs(case_dir, rev_dir)

if __name__ == '__main__':
    main()
