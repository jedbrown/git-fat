#!/usr/bin/env python3

import argparse
import sys
import os
import subprocess
from typing import List
from pathlib import Path
from git_fat.utils import FatRepo, NoArgs
from importlib.metadata import version

__version__ = version("git-fat")

fatrepo: FatRepo


class NotInGitrepo(Exception):
    "Raised when working directory is not part of a git-repo tree"
    pass


def get_gitroot() -> Path:
    try:
        gitroot_check_output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
        gitroot = gitroot_check_output.strip()
        return Path(str(gitroot))
    except subprocess.CalledProcessError:
        raise NotInGitrepo


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


def init_cmd(_):
    print("git-fat: Configured clean and smudge filter", file=sys.stderr)
    with fatrepo.gitapi.config_writer() as cw:
        cw.set_value('filter "fat"', "clean", "git fat filter-clean")
        cw.set_value('filter "fat"', "smudge", "git fat filter-smudge")


def clean_cmd(_):
    fatrepo.filter_clean(sys.stdin.buffer, sys.stdout.buffer)


def smudge_cmd(_):
    fatrepo.filter_smudge(sys.stdin.buffer, sys.stdout.buffer)


def push_cmd(_):
    fatrepo.push()


def pull_cmd(args):
    if getattr(args, "all", None):
        print("git-fat pull: downloading and restoring all files in remote fatstore", file=sys.stderr)
        fatrepo.pull_all()
        return
    if getattr(args, "files", None):
        fpaths = get_valid_fpaths(args.files)
        fatrepo.pull(fpaths)
        return

    print("git-fat pull: use --all or pass list files", file=sys.stderr)
    sys.exit(1)


def fscheck_cmd(args):
    if getattr(args, "files", None):
        fpaths = get_valid_fpaths(args.files)
        fatrepo.fatstore_check(fpaths)
        return
    fatrepo.fatstore_check(NoArgs())


def fscheck_new_cmd(args):
    if getattr(args, "ref_name", None):
        given_ref = fatrepo.gitapi.commit(args.ref_name)
        fatrepo.fatstore_check(given_ref)


def fspublish_new_cmd(args):
    if getattr(args, "ref_name", None):
        given_ref = fatrepo.gitapi.commit(args.ref_name)
        fatrepo.publish_added_fatobjs(given_ref)


def main():
    parser = argparse.ArgumentParser(description="Large (fat) file manager for git")
    parser.add_argument("-v", "--version", action="store_true", help="Show package version")
    subparsers = parser.add_subparsers()
    pull_parser = subparsers.add_parser("pull", help="Download and restore large files from fatstore")
    pull_parser.add_argument("-a", "--all", action="store_true", help="Download and restore all large files")
    pull_parser.add_argument("files", nargs="*", help="List of files to download and restore")
    push_parser = subparsers.add_parser("push", help="Upload large files to fatstore")
    init_parser = subparsers.add_parser("init", help="Configure fat clean and smudge filters for git")
    clean_parser = subparsers.add_parser(
        "filter-clean", help="Takes byte stream (STDIN) and spits out (STDOUT) corresponding fatstub"
    )
    smudge_parser = subparsers.add_parser(
        "filter-smudge", help="Takes fatstub byte stream (STDIN) and spits out (STDOUT) corresponding bytes file"
    )
    fscheck = subparsers.add_parser("fscheck", help="Checks all files or passed files are on remote fatstore")
    fscheck.add_argument("files", nargs="*", help="List of files to check")

    fscheck_new = subparsers.add_parser(
        "fscheck-new",
        help="Checks new fatobjs to given REF (default=master) vs HEAD are on remote fatstore",
    )
    fscheck_new.add_argument("ref_name", nargs="?", default="master")
    fspublish_new = subparsers.add_parser(
        "fspublish-new",
        help="Publish new fatobjs to given REF (default=master) vs HEAD to remote smudge stroe",
    )
    fspublish_new.add_argument("ref_name", nargs="?", default="master")

    pull_parser.set_defaults(func=pull_cmd)
    push_parser.set_defaults(func=push_cmd)
    init_parser.set_defaults(func=init_cmd)
    clean_parser.set_defaults(func=clean_cmd)
    smudge_parser.set_defaults(func=smudge_cmd)
    fscheck.set_defaults(func=fscheck_cmd)
    fscheck_new.set_defaults(func=fscheck_new_cmd)
    fspublish_new.set_defaults(func=fspublish_new_cmd)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    if args.version:
        print(__version__)
        sys.exit(0)

    global fatrepo
    fatrepo = get_fatrepo()
    args.func(args)


if __name__ == "__main__":
    main()
