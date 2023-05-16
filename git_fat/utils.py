from git.repo import Repo
import git.objects
from pathlib import Path
import hashlib
from typing import Union, List, Set, Tuple, IO
import configparser as iniparser
import tempfile
import os
import sys

BLOCK_SIZE = 4096


def umask():
    """Get umask without changing it."""
    old = os.umask(0)
    os.umask(old)
    return old


def tostr(s, encoding="utf-8") -> str:
    """Automate unicode conversion"""
    if isinstance(s, str):
        return s
    if hasattr(s, "decode"):
        return s.decode(encoding)
    raise ValueError("Cound not decode")


def tobytes(s, encoding="utf8") -> bytes:
    """Automatic byte conversion"""
    if isinstance(s, bytes):
        return s
    if hasattr(s, "encode"):
        return s.encode(encoding)
    raise ValueError("Could not encode")


class FatRepo:
    def __init__(self, directory: str):
        self.gitapi = Repo(directory, search_parent_directories=True)
        self.git_root = self.gitapi.git.rev_parse("--show-toplevel")
        self.workspace = Path(self.git_root)
        self.gitfat_config_path = self.workspace / ".gitfat"
        self.gitfat_config = self.get_gitfat_config()
        self.magiclen = self.get_magiclen()
        self.cookie = b"#$# git-fat"
        self.objdir = self.workspace / ".git" / "fat/objects"
        self.debug = True if os.environ.get("GIT_FAT_VERBOSE") else False
        self.setup()

    def verbose(self, *args, force: bool = False, **kargs):
        if force or self.debug:
            return print(*args, file=sys.stderr, **kargs)

    def encode_fatstub(self, digest: str, size: float) -> str:
        """
        Returns a string containg the git-fat stub of a file cleaned with the git-fat filter.
        I.E. #$# git-fat file_hex_digest file_size
            Parameters:
                sha_digest (str): sha Sum of file
                size (float): Size of file in bytes
        """
        return "#$# git-fat %s %20d\n" % (digest, size)

    def decode_fatstub(self, string: str) -> Tuple[str, Union[int, None]]:
        """
        Returns the sha digest and size of a file that's been smudged by the git-fat filter
            Parameters:
                string: Git fat stub string
        """

        parts = string[len(self.cookie) :].split()
        sha_digest = parts[0]
        bytes = int(parts[1]) if len(parts) > 1 else None
        return sha_digest, bytes

    def get_magiclen(self) -> int:
        """
        Returns an interger that is equal to the length of the git-fat stub (74)
        """
        dummy_file_contents = b"dummy"
        dummy_file_sha = hashlib.sha1(b"dummy").hexdigest()
        dummy_file_size = len(dummy_file_contents)
        return len(self.encode_fatstub(dummy_file_sha, dummy_file_size))

    def get_gitfat_config(self):
        gitfat_config = iniparser.ConfigParser()
        gitfat_config.read(self.gitfat_config_path)

        if len(gitfat_config.sections()) != 1:
            raise Exception("Invalid gitfat config")

        return gitfat_config

    def is_fatstore_s3(self):
        return "s3" in self.gitfat_config.sections()

    def is_fatfile(self, filename: str):
        file_filters = self.gitapi.git.execute(
            command=["git", "check-attr", "filter", "--", filename],
            stdout_as_string=True,
        )
        return "filter: fat" in str(file_filters)

    def is_fatblob(self, item):
        if item.type != "blob":
            return False

        if item.size != self.magiclen:
            return False

        fatstub_candidate = item.data_stream.read(self.magiclen)
        return self.is_fatstub(fatstub_candidate)

    def get_all_git_references(self) -> List[str]:
        return [str(ref) for ref in self.gitapi.refs]

    def get_fatobjs(self, refs: Union[str, git.objects.commit.Commit, None] = None) -> Set[git.objects.Blob]:
        """
        Returns a filtered list of GitPython blob objects categorized as git-fat blobs.
        see: https://gitpython.readthedocs.io/en/stable/reference.html?highlight=size#module-git.objects.base
            Parameters:
                refs: A valid Git reference or list of references defaults to HEAD
        """
        refs = "HEAD" if refs is None else refs
        objects = set()

        for commit in self.gitapi.iter_commits(refs):
            fat_blobs = (item for item in commit.tree.traverse() if self.is_fatblob(item))
            objects.update(fat_blobs)
        return objects

    def setup(self):
        if not self.objdir.exists():
            self.objdir.mkdir(mode=0o755, parents=True)

    def clean(self):
        pass

    def is_fatstub(self, data: bytes) -> bool:
        cookie = data[: len(self.cookie)]
        if len(data) != self.magiclen:
            return False
        return cookie == self.cookie

    def store_fatobj(self, cached_file: str, file_sha_digest: str):
        objfile = self.objdir / file_sha_digest
        if objfile.exists():
            self.verbose(f"git-fat filter-clean: cache already exists {objfile}", force=True)
            os.remove(cached_file)
            return

        # Set permissions for the new file using the current umask
        os.chmod(cached_file, int("444", 8) & ~umask())
        os.rename(cached_file, objfile)
        self.verbose(
            f"git-fat filter-clean: caching to {objfile.relative_to(self.workspace)}",
            force=True,
        )

    def filter_clean(self, input_handle: IO, output_handle: IO):
        """
        Takes IO byte stream (input_handle), writes git-fat file stub (sha-magic) bytes on output_handle
        """
        first_block = input_handle.read(BLOCK_SIZE)
        if self.is_fatstub(first_block):
            output_handle.write(first_block)
            return

        fd, tmp_filepath = tempfile.mkstemp(dir=self.objdir)
        sha = hashlib.new("sha1")
        sha.update(first_block)
        fat_size = len(first_block)

        with os.fdopen(fd, "wb") as cached_fatobj:
            cached_fatobj.write(first_block)
            while True:
                block = input_handle.read(BLOCK_SIZE)
                if not block:
                    break
                sha.update(block)
                fat_size += len(block)
                cached_fatobj.write(block)
            cached_fatobj.flush()

        sha_digest = sha.hexdigest()
        self.store_fatobj(tmp_filepath, sha_digest)
        fatstub = self.encode_fatstub(sha_digest, fat_size)
        # output clean bytes (fatstub) to output_handle
        output_handle.write(tobytes(fatstub))

    def smudge(self):
        pass

    def filter_smudge(self, input_handle: IO, output_handle: IO):
        """
        Takes IO byte stream (git-fat file stub), writes full file contents on output_handle
        """
        fatstub_candidate = input_handle.read(self.magiclen)
        input_handle.close()
        if not self.is_fatstub(fatstub_candidate):
            self.verbose("Not a git-fat object")
            self.verbose("git-fat filter-smudge: fat stub not found in input stream")
            return

        sha_digest, size = self.decode_fatstub(fatstub_candidate)
        fatobj = self.objdir / tostr(sha_digest)
        if not fatobj.exists:
            self.verbose("git-fat filter-smudge: fat object missing, maybe pull?")
            return

        read_size = 0
        with open(fatobj, "rb") as cached_fatobj:
            while True:
                block = cached_fatobj.read(BLOCK_SIZE)
                if not block:
                    break
                output_handle.write(block)
                read_size += len(block)

        relative_obj = fatobj.relative_to(self.workspace)
        if read_size == size:
            self.verbose(
                f"git-fat filter-smudge: restoring file from: {relative_obj}",
                force=True,
            )
        else:
            self.verbose(
                f"git-fat filter-smudge: invalid file size of {relative_obj}, expected: {size}, got: {read_size}",
                froce=True,
            )

    def is_on_remote_cache(self, fat_sha_digets):
        pass

    def status(self):
        pass
