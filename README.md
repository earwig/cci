This repository contains tools used in processing
[Contributor copyright investigations](https://en.wikipedia.org/wiki/Wikipedia:Contributor_copyright_investigations)
on Wikipedia.

# Assisted culling

## Installation

    python3 -m venv venv
    . venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install colorama mwparserfromhell pywikiapi PyYAML requests tqdm

## Usage

Every command has a basic help page covering options with `--help`.

    python -m cci.fetch_cci "Case title" -o <name>
    python -m cci.fetch_diffs <name>
    python -m cci.build_edits <name>
    python -m cci.cull_diffs <name> --batch <batch>
    python -m cci.apply_cull <name> -c "Case title" -p <subpage> --batch <batch>
