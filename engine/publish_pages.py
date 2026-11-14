#!/usr/bin/env python3
"""Publish only walkthrough/ to gh-pages. Requires explicit public-publish authorization.
Run after render.py; no model key, raw logs or receipt data files are deployed.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE = 'git@github.com:nicholsss/junction.git'


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout


def main():
    with tempfile.TemporaryDirectory(prefix='review-receipt-pages-') as temp:
        folder = Path(temp)
        exists = run('git', 'ls-remote', '--heads', REMOTE, 'gh-pages').strip()
        if exists:
            run('git', 'clone', '--single-branch', '--branch', 'gh-pages', REMOTE, temp)
        else:
            run('git', 'init', '-b', 'gh-pages', cwd=temp)
            run('git', 'remote', 'add', 'origin', REMOTE, cwd=temp)
        for path in (ROOT / 'walkthrough').iterdir():
            if path.is_file():
                shutil.copy2(path, folder / path.name)
        (folder / '.nojekyll').touch()
        run('git', 'add', '--', 'index.html', '.nojekyll', cwd=temp)
        if run('git', 'diff', '--cached', '--name-only', cwd=temp).strip():
            run('git', 'commit', '-m', 'Publish focused Review Receipt reference', cwd=temp)
            run('git', 'push', 'origin', 'gh-pages', cwd=temp)
    print('Published gh-pages: https://nicholsss.github.io/junction/')


if __name__ == '__main__':
    main()
