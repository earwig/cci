#!/usr/bin/env python3

import argparse
import gzip
import json
from pathlib import Path
import re

from . import utils
from .case import Edit

_LINK_ROOT = 'toolforge:earwig-dev/cci'

def apply_cull(root: Path, case_name: str, case_page: str, batch: int):
    key = f'cull/batch-{batch:02}/page-{case_page}'
    cull_path = root / f'{key}.json.gz'
    html_path = root / f'{key}.html'

    with gzip.open(cull_path, 'rt') as fp:
        edits = [Edit.load(edit) for edit in json.load(fp)]

    title = f'{utils.CCI_PREFIX}{case_name}'
    if int(case_page) != 1:
        title += f' {case_page}'
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

    # TODO: remove empty sections?

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

    with html_path.open('w') as htmlfp:
        info = json.dumps([edit.dump() for edit in edits], indent=4).replace('<', '&lt;')
        htmlfp.write(f'<pre>\n{info}\n</pre>')

def main():
    parser = argparse.ArgumentParser(description='Apply a cull to a case page and generate a diff')
    parser.add_argument('case', help='Case dir')
    parser.add_argument('-c' , '--case-name', required=True, help='Case name')
    parser.add_argument('-p', '--case-page', metavar='INDEX', required=True,
                        help='Case page')
    parser.add_argument('-b', '--batch', metavar='NUM', type=int, required=True,
                        help='Batch number')
    args = parser.parse_args()
    utils.setup_logging()

    root = Path(args.case)
    apply_cull(root, args.case_name, args.case_page, args.batch)

if __name__ == '__main__':
    main()
