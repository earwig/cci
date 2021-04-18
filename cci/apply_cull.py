#!/usr/bin/env python3

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import List, Optional

import jinja2

from . import utils
from .case import Edit

_LINK_ROOT = 'toolforge:earwig-dev/cci'

def apply_cull(root: Path, case_name: str, case_page: Optional[str], batch: str, skip_edits: bool):
    dirname = f'cull/batch-{batch.zfill(2)}'
    if case_page:
        case_pages = [case_page]
    else:
        case_pages = [
            re.match(r'page-(\d+).json.gz', name.name).group(1)
            for name in (root / dirname).iterdir()
            if name.name.endswith('.json.gz')
        ]

    for name in case_pages:
        _apply_cull(root, dirname, case_name, name, batch, skip_edits)

def _apply_cull(
    root: Path,
    dirname: str,
    case_name: str,
    case_page: str,
    batch: str,
    skip_edits: bool,
):
    key = f'{dirname}/page-{case_page}'
    cull_path = root / f'{key}.json.gz'
    html_path = root / f'{key}.html'

    with gzip.open(cull_path, 'rt') as fp:
        edits = [Edit.load(edit) for edit in json.load(fp)]

    title = f'{utils.CCI_PREFIX}{case_name}'
    if int(case_page) != 1:
        title += f' {case_page}'

    if not skip_edits:
        _build_edit(root, key, title, edits)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent / 'templates'),
        autoescape=jinja2.select_autoescape(['html', 'xml'])
    )
    env.filters['titleencode'] = lambda title: title.replace(' ', '_')
    template = env.get_template('viewer.html')

    with html_path.open('w') as htmlfp:
        htmlfp.write(template.render(
            case=root.name,
            name=case_name,
            page=case_page,
            prefix=utils.CCI_PREFIX,
            title=title,
            batch=f'batch {batch}',
            path=cull_path.name,
            static_url=_static_url,
        ))

def _build_edit(root: Path, key: str, title: str, edits: List[Edit]):
    revid, content = utils.get_title_revision(title)

    total_diffs = content.count('[[Special:Diff/')
    removed_diffs = 0
    lines = content.strip().splitlines()
    for i, line in reversed(list(enumerate(lines))):
        changed = False
        page = ''
        for edit in edits:
            if f'[[Special:Diff/{edit.diff}|' in line:
                line = re.sub(rf'\[\[Special:Diff/{edit.diff}\|\(\+\d+\)\]\]', '', line)
                changed = True
                page = edit.page
                removed_diffs += 1
        if changed:
            if 'Special:Diff' not in line and re.fullmatch(
                    rf"\*('''N''' )?\[\[:{re.escape(page)}\]\] \(\d+ edits?\): ", line):
                lines.pop(i)
            else:
                lines[i] = line

    has_content = False
    last_header = None
    for i, line in reversed(list(enumerate(lines))):
        if line.startswith('=== Pages '):
            if has_content:
                has_content = False
            elif last_header:
                # Remove empty section
                for _ in range(last_header - i):
                    lines.pop(i)
            last_header = i
        elif line:
            has_content = True

    content = '\n'.join(lines) + '\n'
    summary = (
        f'tool-assisted cull: -{removed_diffs}/{total_diffs} diffs '
        f'([[{_LINK_ROOT}/{root.name}/{key}.html|more info]])'
    )
    print(json.dumps({
        'title': title,
        'content': content,
        'revid': revid,
        'summary': summary,
    }))

def _static_url(filename: str) -> str:
    with (Path(__file__).parent.parent / 'static' / filename).open('rb') as fp:
        fhash = hashlib.sha1(fp.read()).hexdigest()
    return f'/cci/static/{filename}?v={fhash}'

def main():
    parser = argparse.ArgumentParser(description='Apply a cull to a case page and generate a diff')
    parser.add_argument('case', help='Case dir')
    parser.add_argument('-c' , '--case-name', help='Case name')
    parser.add_argument('-p', '--case-page', metavar='INDEX', help='Case page')
    parser.add_argument('-b', '--batch', metavar='NAME', required=True,
                        help='Batch number or name')
    parser.add_argument('--skip-edits', action='store_true',
                        help='Skip generating edits to apply on-wiki')
    args = parser.parse_args()
    utils.setup_logging()

    root = Path(args.case)
    apply_cull(root, args.case_name, args.case_page, args.batch, args.skip_edits)

if __name__ == '__main__':
    main()
