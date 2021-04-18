#!/usr/bin/env python3

import argparse
import logging
import math
from pathlib import Path
import re
from typing import List, Optional

import mwparserfromhell
import tqdm

from . import utils
from .case import Case, CasePage, Diff, Page, Section

_IGNORED_HEADINGS = ['Instructions', 'Background', 'Contribution survey']

def fetch_cci(name: str, recursive: bool = True) -> Case:
    title = utils.CCI_PREFIX + name
    logging.info('fetching main case page')
    content = utils.get_title_content(title)
    tree = mwparserfromhell.parse(content)

    subpages: List[str] = sorted(
        link.title for link in tree.filter_wikilinks()
        if link.title.startswith(title)
        and not link.title.endswith('CCI cleanup')
    )
    if subpages and recursive:
        indices = {subtitle[len(title):].strip(): subtitle for subtitle in subpages}
        assert all(re.match(r'^\d+$', index) for index in indices), indices
        numlen = math.ceil(math.log10(len(subpages)))
        firstname = '1'.zfill(numlen)
        assert firstname not in indices, indices
        trees = {firstname: tree}
        logging.info('fetching case subpages...')
        for index, subtitle in tqdm.tqdm(indices.items(), unit='pages'):
            subcontent = utils.get_title_content(subtitle)
            trees[index] = mwparserfromhell.parse(subcontent)
    else:
        trees = {'main': tree}

    logging.info('parsing cases...')
    pages = {}
    for index, tree in tqdm.tqdm(trees.items(), unit='pages'):
        try:
            page = _parse_case_page(index, name, tree)
        except Exception:
            logging.error(f'failed to parse case page {index}')
            raise
        if not page:
            continue
        pages[index] = page

    return Case(pages)

def _parse_case_page(index: str, name: str,
                     tree: mwparserfromhell.wikicode.Wikicode) -> Optional[CasePage]:
    diff_sections = tree.get_sections(matches=lambda title: title.matches(name))
    if not diff_sections and '<!-- Template:Courtesy blanked -->' in tree:
        return None
    assert len(diff_sections) == 1, tree.filter_headings()
    diff_section = diff_sections[0]
    assert diff_section.nodes[0].level == 2

    excluded = [diff_section]
    unknown = []
    for section in tree.get_sections(include_lead=False):
        if any(section in excl for excl in excluded):
            continue
        if section.nodes[0].title.matches(_IGNORED_HEADINGS):
            excluded.append(section)
        else:
            unknown.append(section)

    unknown = [section for section in unknown if not any(section in excl for excl in excluded)]
    assert not unknown, [section.nodes[0] for section in unknown]

    sections = {}
    for section in diff_section.get_sections(levels=[3]):
        title = section.nodes[0].title.strip()
        match = re.match(r'^Pages (\d+) through (\d+)$', title)
        assert match, title
        index = f'{match.group(1)}-{match.group(2)}'
        lines = [line.strip() for line in section.splitlines()[1:] if line.strip()]
        if _is_collapsed(lines):
            continue
        pages = [_parse_line(line) for line in lines]
        pages = [line for line in pages if line]
        if not pages:
            continue
        sections[index] = Section(title, pages)

    return CasePage(index, sections)

def _is_collapsed(lines: List[str]) -> bool:
    if not lines:
        return False
    first, last = lines[0].lower(), lines[-1].lower()
    if last.startswith('this report generated by') and len(lines) > 1:
        last = lines[-2]
    return (
        ('{{collapse top' in first or '{{ctop' in first) and
        ('{{collapse bottom' in last or '{{cbot' in last)
    )

def _parse_line(line: str) -> Optional[Page]:
    if not line.startswith('*'):
        return None
    tree = mwparserfromhell.parse(line)
    if any(tmpl.name.matches(('Y', 'N', '?')) for tmpl in tree.filter_templates()):
        return None
    links = tree.filter_wikilinks()
    page = links[0]
    assert page.text is None, page
    assert not page.title.startswith('Special:'), page.title
    diffs = [_parse_diff(link) for link in links[1:]]

    return Page(
        title=page.title.lstrip(':'),
        diffs=diffs,
    )

def _parse_diff(link: mwparserfromhell.nodes.Wikilink) -> Diff:
    assert link.title.startswith('Special:Diff/'), link
    revid: str = link.title.split('/', 1)[1]
    size = str(link.text)
    assert re.match(r'^\d+$', revid), link
    assert re.match(r'^\([+-]\d+\)$', size), link

    return Diff(
        revid=int(revid),
        size=size[1:-1],
    )

def main():
    parser = argparse.ArgumentParser(description='Fetch a CCI')
    parser.add_argument('name', help='Case name')
    parser.add_argument('-o', '--output', help='Case output dir', required=True)
    parser.add_argument('--no-recursive', action='store_true',
                        help='Only process the top-level case page')
    args = parser.parse_args()
    utils.setup_logging()

    root = Path(args.output)
    case_dir = root / 'case'
    case_dir.mkdir(parents=True, exist_ok=True)

    case = fetch_cci(args.name, recursive=not args.no_recursive)

    logging.info('saving')
    case.save(case_dir)

if __name__ == '__main__':
    main()
