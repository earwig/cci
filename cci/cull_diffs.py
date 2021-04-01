#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
import functools
import gzip
import json
import logging
import operator
from pathlib import Path
import re
from typing import List, Optional

from colorama import Fore
import mwparserfromhell
import tqdm
import yaml

from . import utils
from .case import CullRule, Delta, Edit, Line

@dataclass
class Filters:
    casepages: Optional[List[str]]
    sections: Optional[List[str]]
    pages: Optional[List[str]]
    diffs: Optional[List[int]]

def cull_diffs(
    edits_path: Path,
    rules_path: Path,
    cull_root: Path,
    filters: Optional[Filters] = None,
    batch: Optional[int] = None,
    verbose: bool = False,
    debug: bool = False,
    hide_culled: bool = False,
    dump_rules: bool = False,
):
    with gzip.open(edits_path, 'rt') as fp:
        edits = [Edit.load(edit) for edit in json.load(fp)]
    with rules_path.open() as fp:
        rules = yaml.load(fp, yaml.CSafeLoader)
    rules['whitelist'] = rules.get('whitelist', '').splitlines()

    logging.info(f'analyzing {len(edits)} diffs to cull...')
    it = edits if verbose else tqdm.tqdm(edits, unit='diffs')
    culled = {}
    for edit in it:
        if filters is not None:
            filtered = False
            for filt, attr in [
                (filters.casepages, edit.casepage),
                (filters.sections, edit.section),
                (filters.pages, edit.page),
                (filters.diffs, edit.diff),
            ]:
                if filt is not None and attr not in filt:
                    filtered = True
                    break
            if filtered:
                continue
        try:
            _cull_edit(edit, rules, verbose, debug, hide_culled)
        except BrokenPipeError:
            raise
        except Exception:
            logging.exception(f'Failed to cull edit: {edit}')
            continue
        if edit.culled:
            culled.setdefault(edit.casepage, []).append(edit)

    logging.info(f'culled {sum(1 for edit in edits if edit.culled)} diffs')
    for index, page_edits in culled.items():
        logging.info(f'- culled {len(page_edits)} diffs in case page {index}')

    if dump_rules:
        rules = {}
        unmatched = set()
        for edit in edits:
            if not edit.delta:
                continue
            for line in edit.delta.lines:
                if line.culled:
                    for rule in line.rules:
                        rules.setdefault(rule.name, set()).add(line.text)
                else:
                    unmatched.add(line.text)
        print('Matched rules:')
        for name, lines in rules.items():
            print()
            print(name)
            for line in sorted(lines):
                print(f'- {line}')
        print()
        if unmatched:
            print('Unmatched lines:')
            for line in sorted(unmatched):
                print(f'- {line}')
        else:
            print('No unmatched lines')

    if batch:
        cull_dir = cull_root / f'batch-{batch:02}'
        cull_dir.mkdir(parents=True, exist_ok=True)
        for index, page_edits in culled.items():
            cull_path = cull_dir / f'page-{index}.json.gz'
            with gzip.open(cull_path, 'wt') as fp:
                json.dump([edit.dump() for edit in page_edits], fp)

def _cull_edit(edit: Edit, rules: dict, verbose: bool, debug: bool, hide_culled: bool):
    before_lines = set(edit.before.raw.splitlines())
    lines = [
        Line(index=i, raw=line, text=line.strip())
        for i, line in enumerate(edit.after.raw.splitlines(), 1)
        if line.strip() and line not in before_lines
    ]
    edit.delta = Delta(lines=lines)

    rule_counts = {}
    for line in lines:
        for item in rules['whitelist']:
            if item in line.text:
                line.text = line.text.replace(item, '')
                line.rules.append(CullRule('whitelist', item))

        for name, rule in rules['rules'].items():
            if cull := _match_rule(line, name, rule, debug):
                if name in rule_counts and 'max' in rule and rule_counts[name] >= rule['max']:
                    continue
                line.rules.append(cull)
                line.culled = True
                rule_counts.setdefault(name, 0)
                rule_counts[name] += 1
                break

    if verbose:
        print(f'Case page {edit.casepage} > {edit.section} > [[{edit.page}]] > {edit.diff}:')
        if edit.culled:
            print(f'  {Fore.GREEN}✓ fully culled: {len(edit.delta.lines)} lines{Fore.RESET}')
        else:
            num_culled = sum(1 for line in edit.delta.lines if line.culled)
            print(f'  {num_culled}/{len(edit.delta.lines)} lines culled')
        print()
        for line in lines:
            if hide_culled and line.culled:
                continue
            print(line)
        print()

def _match_rule(line: Line, name: str, rule: dict, debug: bool) -> Optional[CullRule]:
    if rule['type'] == 'regex':
        return _match_regex(line, name, rule, debug)
    if rule['type'] == 'refs':
        return _match_refs(line, name, rule)
    raise NotImplementedError(rule['type'])

def _match_regex(line: Line, name: str, rule: dict, debug: bool) -> Optional[CullRule]:
    if 'pre' in rule:
        text = _preprocess_wikitext(rule['pre'], line.text)
    else:
        text = line.text
    if 'sub' in rule:
        for pat, repl in rule['sub']:
            text = re.sub(pat, repl, text)
    patterns = [rule['match']] if isinstance(rule['match'], str) else rule['match']
    if 'flags' in rule:
        raw_flags = [rule['flags']] if isinstance(rule['flags'], str) else rule['flags']
        flags = functools.reduce(operator.or_, [re.RegexFlag[flag] for flag in raw_flags])
    else:
        flags = re.IGNORECASE
    for pattern in patterns:
        if debug:
            logging.info(f'try pattern {pattern!r} against text {text!r}')
        if re.fullmatch(pattern, text, flags=flags):
            return CullRule(name, f'regex match: {pattern}')
    return None

@functools.cache
def _preprocess_wikitext(mode: str, text: str) -> str:
    tree = mwparserfromhell.parse(text)

    if mode == 'strip':
        _strip_links(tree)
        _strip_tags(tree)
    elif mode == 'deref':
        for tag in tree.filter_tags():
            if tag.tag == 'ref':
                _strip_links(tree)
        _strip_tags(tree)
    elif mode == 'deextlink':
        _strip_ext_links(tree)
    else:
        raise NotImplementedError(mode)

    return re.sub(r'\s+', ' ', str(tree))

def _strip_links(tree: mwparserfromhell.wikicode.Wikicode):
    _strip_templates(tree)
    _strip_wikilinks(tree)
    _strip_ext_links(tree)

def _strip_templates(tree: mwparserfromhell.wikicode.Wikicode, threshold: int = 30):
    for template in tree.filter_templates(recursive=tree.RECURSE_OTHERS):
        for param in reversed(template.params):
            if len(param.name) < threshold and len(param.value) < threshold:
                template.remove(param)
        if not template.params and len(template.name) < threshold:
            _tree_remove(tree, template)

def _strip_wikilinks(tree: mwparserfromhell.wikicode.Wikicode, threshold: int = 50):
    for link in tree.filter_wikilinks():
        if len(link.title) < threshold and (link.text is None or len(link.text) < threshold):
            _tree_remove(tree, link)

def _strip_ext_links(tree: mwparserfromhell.wikicode.Wikicode,
                     threshold: int = 250, url_threshold: int = 1000):
    for link in tree.filter_external_links():
        if len(link.url) < url_threshold and (link.title is None or len(link.title) < threshold):
            _tree_remove(tree, link)

def _strip_tags(tree: mwparserfromhell.wikicode.Wikicode, threshold: int = 200):
    for tag in tree.filter_tags():
        if tag.tag != 'ref' and not tag.attributes:
            tree.replace(tag, tag.contents)

    for tag in tree.filter_tags():
        if tag.tag == 'ref' and len(tag.contents) < threshold:
            _tree_remove(tree, tag)

def _tree_remove(tree: mwparserfromhell.wikicode.Wikicode, node: mwparserfromhell.nodes.Node):
    try:
        tree.remove(node)
    except ValueError:
        pass

def _match_refs(line: Line, name: str, rule: dict, threshold: int = 30) -> Optional[CullRule]:
    if not line.text.startswith('*'):
        return None
    text = _preprocess_wikitext('strip', line.text.lower())
    for journal in rule['journals']:
        if journal in text:
            for title in rule['titles']:
                if title in text:
                    if len(text.replace(journal, '').replace(title, '')) < threshold:
                        return CullRule(name, 'bibliography match')
    return None

def main():
    parser = argparse.ArgumentParser(description='Cull diffs for CCI')
    parser.add_argument('case', help='Case dir')
    filt = parser.add_argument_group('filtering')
    filt.add_argument('-c', '--case-page', dest='casepages', metavar='INDEX', action='append',
                      help='Examine these case page(s)')
    filt.add_argument('-s', '--section', dest='sections', metavar='NAME', action='append',
                      help='Examine these case sections(s)')
    filt.add_argument('-p', '--page', dest='pages', metavar='TITLE', action='append',
                      help='Examine these page(s)')
    filt.add_argument('-d', '--diff', dest='diffs', metavar='REVID', action='append', type=int,
                      help='Examine these diff(s)')
    outp = parser.add_argument_group('output')
    outp.add_argument('-b', '--batch', metavar='NUM', type=int, help='Batch number')
    outp.add_argument('-v', '--verbose', action='store_true', help='Show details')
    outp.add_argument('-g', '--debug', action='store_true', help='Show even more details')
    outp.add_argument('--hide-culled', action='store_true', help='Hide culled lines')
    outp.add_argument('--dump-rules', action='store_true', help='Dump matched rule info')
    args = parser.parse_args()
    utils.setup_logging()

    root = Path(args.case)
    filters = Filters(
        casepages=args.casepages,
        sections=args.sections,
        pages=args.pages,
        diffs=args.diffs,
    )
    cull_diffs(
        root / 'edits.json.gz', root / 'rules.yaml', root / 'cull',
        filters=filters,
        batch=args.batch,
        verbose=args.verbose,
        debug=args.debug,
        hide_culled=args.hide_culled,
        dump_rules=args.dump_rules,
    )

if __name__ == '__main__':
    main()
