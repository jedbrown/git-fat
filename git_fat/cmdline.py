#!/usr/bin/env python3

import argparse
import sys
import os
import subprocess
from typing import List
from pathlib import Path
from git_fat.utils import FatRepo

fatrepo: FatRepo


def get_gitroot() -> Path:
    try:
        gitroot_check_output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
        gitroot = gitroot_check_output.strip()
        return Path(str(gitroot))
    except subprocess.CalledProcessError:
        sys.exit(1)


def get_fatrepo() -> FatRepo:
    gitroot = get_gitroot()
    return FatRepo(gitroot)


def get_valid_fpaths(files: List[str]) -> List[Path]:
    fpaths = []
    curdir = Path(os.path.abspath(os.path.curdir))
    for file in files:
        if not os.path.exists(file):
            print(f"git-fat: {file} not found, is given path valid?", file=sys.stderr)
            continue
        fpaths.append(curdir / file)

    if len(fpaths) == 0:
        print("git-fat pull: no valid file paths given", file=sys.stderr)
        sys.exit(1)

    return fpaths


def init_cmd(args):
    print("Configuring fat git filters")


def clean_cmd():
    print("running clean")


def smudge_cmd():
    print("running smudge")


def push_cmd(args):
    if len(args) > 0:
        print("git-fat push: takes no additional arguments", file=sys.stderr)
        sys.exit(1)
    fatrepo.push()


def pull_cmd(args):
    if args.all:
        print("git-fat pull: downloading and restoring all files in remote fatstore", file=sys.stderr)
        fatrepo.pull_all()
        return
    if args.files:
        fpaths = get_valid_fpaths(args.files)
        fatrepo.pull(fpaths)
        return

    print("git-fat pull: use --all or pass list files", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Large (fat) file manager for git")
    subparsers = parser.add_subparsers()
    pull_parser = subparsers.add_parser("pull", help="Download and restore large files from fatstore")
    pull_parser.add_argument("-a", "--all", action="store_true", help="Download and restore all large files")
    pull_parser.add_argument("files", nargs="*", help="List of files to download and restore")
    push_parser = subparsers.add_parser("push", help="Upload large files to fatstore")
    init_parser = subparsers.add_parser("init", help="Configure fat clean and smudge filters for git")
    clean_parser = subparsers.add_parser(
        "filter-clean", help="Takes byte stream (STDIN) and spits out (STDOUT) corresponding fatstub"
    )
    pull_parser.set_defaults(func=pull_cmd)
    push_parser.set_defaults(func=push_cmd)
    init_parser.set_defaults(func=init_cmd)
    clean_parser.set_defaults(func=clean_cmd)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    global fatrepo
    fatrepo = get_fatrepo()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
