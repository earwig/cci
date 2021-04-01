import logging
from typing import Tuple

from . import site

CCI_PREFIX = 'Wikipedia:Contributor copyright investigations/'

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d [%(levelname)-7s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

def get_title_content(title: str) -> str:
    gen = site.query(
        titles=[title],
        prop='revisions',
        rvprop='content',
        rvlimit=1,
        rvslots='main',
    )
    return next(gen).pages[0].revisions[0].slots.main.content

def get_title_revision(title: str) -> Tuple[int, str]:
    gen = site.query(
        titles=[title],
        prop='revisions',
        rvprop='ids|content',
        rvlimit=1,
        rvslots='main',
    )
    rev = next(gen).pages[0].revisions[0]
    return (rev.revid, rev.slots.main.content)
