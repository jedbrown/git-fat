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


def verbose_stderr(*args, **kwargs):
    return print(*args, file=sys.stderr, **kwargs)


def verbose_ignore(*args, **kwargs):
    pass


def umask():
    """Get umask without changing it."""
    old = os.umask(0)
    os.umask(old)
    return old


def touni(s, encoding="utf8"):
    """Automate unicode conversion"""
    if isinstance(s, str):
        return s
    if hasattr(s, "decode"):
        return s.decode(encoding)
    raise ValueError("Cound not decode")


def tobytes(s, encoding="utf8"):
    """Automatic byte conversion"""
    if isinstance(s, bytes):
        return s
    if hasattr(s, "encode"):
        return s.encode(encoding)
    raise ValueError("Could not encode")


class FatRepo:
    def __init__(self, directory: str):
        self.gitapi = Repo(directory)
        self.workspace = Path(directory)
        self.gitfat_config_path = self.workspace / ".gitfat"
        self.gitfat_config = self.get_gitfat_config()
        self.magiclen = self.get_magiclen()
        self.cookie = "#$# git-fat"
        self.objdir = self.workspace / ".git" / "fat/objects"
        self.verbose = (
            verbose_stderr if os.environ.get("GIT_FAT_VERBOSE") else verbose_ignore
        )

    def encode_fatstub(self, digest: str, size: float) -> str:
        """
        Returns a string containg the git-fat stub of a file cleaned with the git-fat filter.
        I.E. #$# git-fat file_hex_digest file_size
            Parameters:
                digest (str): SHA1 Sum of file
                size (float): Size of file in bytes
        """
        return "#$# git-fat %s %20d\n" % (digest, size)

    def get_magiclen(self) -> int:
        """
        Returns an interger that is equal to the length of the git-fat stub (74)
        """
        dummy_file_contents = b"dummy"
        dummy_file_sha1 = hashlib.sha1(b"dummy").hexdigest()
        dummy_file_size = len(dummy_file_contents)
        return len(self.encode_fatstub(dummy_file_sha1, dummy_file_size))

    def decode_fatstub(self, string: str) -> Tuple[str, Union[int, None]]:
        """
        Returns the SHA1 hex digest and size of a file that's been smudged by the git-fat filter
            Parameters:
                string: Git fat stub string
        """

        parts = string[len(self.cookie) :].split()
        digest = parts[0]
        bytes = int(parts[1]) if len(parts) > 1 else None
        return digest, bytes

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

        return item.data_stream.read().decode().startswith(self.cookie)

    def get_all_git_references(self) -> List[str]:
        return [str(ref) for ref in self.gitapi.refs]

    def get_fatobj(
        self, refs: Union[str, git.objects.commit.Commit, None] = None
    ) -> Set[git.objects.Blob]:
        """
        Returns a filtered list of GitPython blob objects categorized as git-fat blobs.
        see: https://gitpython.readthedocs.io/en/stable/reference.html?highlight=size#module-git.objects.base
            Parameters:
                refs: A valid Git reference or list of references defaults to HEAD
        """
        refs = "HEAD" if refs is None else refs
        objects = set()

        for commit in self.gitapi.iter_commits(refs):
            fat_blobs = (
                item for item in commit.tree.traverse() if self.is_fatblob(item)
            )
            objects.update(fat_blobs)
        return objects

    def setup(self):
        pass

    def clean(self):
        pass

    def is_fatstub(self, data: bytes) -> bool:
        if len(data) != self.magiclen:
            return False
        if not str(data).startswith(self.cookie):
            return False
        return True

    def store_fatobj(self, cached_file: str, file_sha1_digest: str):
        objfile = self.objdir / file_sha1_digest
        if not os.path.exists(objfile):
            # Set permissions for the new file using the current umask
            os.chmod(cached_file, int("444", 8) & ~umask())
            os.rename(cached_file, objfile)
            self.verbose(f"git-fat filter-clean: caching to {objfile}")
        else:
            self.verbose(f"git-fat filter-clean: cache already exists {objfile}")

        os.remove(cached_file)

    def filter_clean(self, input_handle: IO, output_handle: IO):
        first_block = input_handle.read(BLOCK_SIZE)
        if self.is_fatstub(first_block):
            output_handle.write(first_block)
            return

        fd, tmp_filepath = tempfile.mkstemp(dir=self.objdir)
        sha1 = hashlib.new("sha1")
        fat_size = 0

        with os.fdopen(fd, "wb") as cached_fatobj:
            cached_fatobj.write(first_block)
            while True:
                block = input_handle.read(BLOCK_SIZE)
                if not block:
                    break
                sha1.update(block)
                fat_size += len(block)
                cached_fatobj.write(block)
            cached_fatobj.flush()

        sha1_digest = sha1.hexdigest()
        self.store_fatobj(tmp_filepath, sha1_digest)
        fatstub = self.encode_fatstub(sha1_digest, fat_size)
        # output clean bytes (fatstub) to output_handle
        output_handle.write(tobytes(fatstub))

    def smudge(self):
        pass

    def status(self):
        pass
