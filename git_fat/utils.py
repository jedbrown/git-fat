from git.repo import Repo
import git.objects
from pathlib import Path
from git_fat.fatstores import S3FatStore
import hashlib
from typing import Union, List, Tuple, IO
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


class FatObj:
    def __init__(self, path: os.PathLike, fatid: str, size: int, abspath: os.PathLike):
        self.fatid = fatid
        self.path = path
        self.abspath = abspath
        self.size = size


class FatRepo:
    def __init__(self, directory: Path):
        self.gitapi = Repo(str(directory), search_parent_directories=True)
        self.workspace = Path(directory)
        self.gitfat_config_path = self.workspace / ".gitfat"
        self.magiclen = self.get_magiclen()
        self.cookie = b"#$# git-fat"
        self.objdir = self.workspace / ".git" / "fat/objects"
        self.debug = True if os.environ.get("GIT_FAT_VERBOSE") else False
        self._gitfat_config = None
        self._fatstore = None
        self.setup()

    @property
    def gitfat_config(self):
        if not self._gitfat_config:
            self._gitfat_config = self.get_gitfat_config()
        return self._gitfat_config

    @property
    def fatstore(self):
        if not self._fatstore:
            self._fatstore = self.get_fatstore()
        return self._fatstore

    def verbose(self, *args, force: bool = False, **kargs):
        if force or self.debug:
            print(*args, file=sys.stderr, **kargs)

    def encode_fatstub(self, digest: str, size: float) -> str:
        """
        Returns a string containg the git-fat stub of a file cleaned with the git-fat filter.
        I.E. #$# git-fat file_hex_digest file_size
            Parameters:
                sha_digest (str): sha Sum of file
                size (float): Size of file in bytes
        """
        return "#$# git-fat %s %20d\n" % (digest, size)

    def decode_fatstub(self, string: str) -> Tuple[str, int]:
        """
        Returns the fatid (sha1 digest) and size of a file that's been smudged by the git-fat filter
            Parameters:
                string: Git fat stub string
        """

        parts = string[len(self.cookie) :].split()
        fatid = parts[0]
        size = int(parts[1]) if len(parts) > 1 else 0
        return fatid, size

    def get_magiclen(self) -> int:
        """
        Returns an interger that is equal to the length of the git-fat stub (74)
        """
        dummy_file_contents = b"dummy"
        dummy_file_sha = hashlib.sha1(b"dummy").hexdigest()
        dummy_file_size = len(dummy_file_contents)
        return len(self.encode_fatstub(dummy_file_sha, dummy_file_size))

    def get_gitfat_config(self) -> iniparser.ConfigParser:
        """
        Returns ConfigParser for gitfat config found in repo
        """
        if not self.gitfat_config_path.exists():
            self.verbose("No valid fat config exists", force=True)
            sys.exit(1)

        gitfat_config = iniparser.ConfigParser()
        gitfat_config.read(self.gitfat_config_path)

        if len(gitfat_config.sections()) != 1:
            raise Exception("Invalid gitfat config")

        return gitfat_config

    def get_fatstore(self):
        # if self.is_fatstore_s3():
        config = dict(self.gitfat_config["s3"])
        return S3FatStore(config)

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

    def create_fatobj(self, blob: git.objects.Blob) -> FatObj:
        fatid, size = self.decode_fatstub(blob.data_stream.read())

        return FatObj(path=blob.path, fatid=tostr(fatid), size=size, abspath=blob.abspath)

    def get_fatobjs(self, refs: Union[str, git.objects.commit.Commit, None] = None) -> List[FatObj]:
        """
        Returns a filtered list of GitPython blob objects categorized as git-fat blobs.
        see: https://gitpython.readthedocs.io/en/stable/reference.html?highlight=size#module-git.objects.base
            Parameters:
                refs: A valid Git reference or list of references defaults to HEAD
        """
        refs = "HEAD" if refs is None else refs
        unique_fatobjs = set()

        for commit in self.gitapi.iter_commits(refs):
            fatobjs = (
                self.create_fatobj(item) for item in commit.tree.traverse() if self.is_fatblob(item)  # type: ignore
            )
            unique_fatobjs.update(fatobjs)
        return list(unique_fatobjs)

    def setup(self):
        if not self.objdir.exists():
            self.objdir.mkdir(mode=0o755, parents=True)

    def is_fatstub(self, data: bytes) -> bool:
        cookie = data[: len(self.cookie)]
        if len(data) != self.magiclen:
            return False
        return cookie == self.cookie

    def cache_fatfile(self, cached_file: str, file_sha_digest: str):
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

        fd, tmpfile_path = tempfile.mkstemp(dir=self.objdir)
        sha = hashlib.new("sha1")
        sha.update(first_block)
        fat_size = len(first_block)

        with os.fdopen(fd, "wb") as tmpfile_handle:
            tmpfile_handle.write(first_block)
            while True:
                block = input_handle.read(BLOCK_SIZE)
                if not block:
                    break
                sha.update(block)
                fat_size += len(block)
                tmpfile_handle.write(block)
            tmpfile_handle.flush()

        sha_digest = sha.hexdigest()
        self.cache_fatfile(tmpfile_path, sha_digest)
        fatstub = self.encode_fatstub(sha_digest, fat_size)
        # output clean bytes (fatstub) to output_handle
        output_handle.write(tobytes(fatstub))

    def filter_smudge(self, input_handle: IO, output_handle: IO):
        """
        Takes IO byte stream (git-fat file stub), writes full file contents on output_handle
        """
        fatstub_candidate = input_handle.read(self.magiclen)
        if not self.is_fatstub(fatstub_candidate):
            self.verbose("Not a git-fat object")
            self.verbose("git-fat filter-smudge: fat stub not found in input stream")
            return

        sha_digest, size = self.decode_fatstub(fatstub_candidate)
        fatfile = self.objdir / tostr(sha_digest)
        if not fatfile.exists:
            self.verbose("git-fat filter-smudge: fat object missing, maybe pull?")
            return

        read_size = 0
        with open(fatfile, "rb") as fatfile_handle:
            while True:
                block = fatfile_handle.read(BLOCK_SIZE)
                if not block:
                    break
                output_handle.write(block)
                read_size += len(block)

        relative_obj = fatfile.relative_to(self.workspace)
        if read_size == size:
            self.verbose(
                f"git-fat filter-smudge: restoring file from: {relative_obj}",
                force=True,
            )
        else:
            self.verbose(
                f"git-fat filter-smudge: invalid file size of {relative_obj}, expected: {size}, got: {read_size}",
                force=True,
            )

    def restore_fatobj(self, obj: FatObj):
        cache = self.objdir / obj.fatid
        self.verbose(f"git-fat pull: restoring {obj.path} from {cache.name}", force=True)
        stat = os.lstat(obj.abspath)
        # force smudge by invalidating lstat in git index
        os.utime(obj.abspath, (stat.st_atime, stat.st_mtime + 1))
        self.gitapi.index.checkout(obj.abspath, force=True, index=True)

    def pull_all(self):
        local_fatfiles = os.listdir(self.objdir)
        remote_fatfiles = self.fatstore.list()
        commited_fatobjs = self.get_fatobjs()

        pull_candidates = [file for file in remote_fatfiles if file not in local_fatfiles]
        if len(pull_candidates) == 0:
            self.verbose("git-fat pull: nothing to pull", force=True)
            return

        for obj in commited_fatobjs:
            if obj.fatid not in pull_candidates or obj.fatid not in remote_fatfiles:
                self.verbose(f"git-fat pull: {obj.path} found locally, skipping", force=True)
                continue
            self.verbose(f"git-fat pull: pulling {obj.path}", force=True)
            self.fatstore.download(obj.fatid, self.objdir / obj.fatid)
            self.restore_fatobj(obj)

    def pull(self, files: List[Path] = []):
        if len(files) == 0:
            self.verbose("git-fat pull: nothing to pull", force=True)
            return

        for fpath in files:
            try:
                relativep = fpath.relative_to(self.gitapi.working_dir)  # type: ignore
                blob = self.gitapi.tree() / str(relativep)
                if not self.is_fatblob(blob):
                    self.verbose(f"git-fat pull: {relativep} is not a fat object", force=True)
                    continue
                obj = self.create_fatobj(blob)  # type: ignore
                self.fatstore.download(obj.fatid, self.objdir / obj.fatid)
                self.restore_fatobj(obj)
            except KeyError:
                self.verbose(f"git-fat pull: {fpath} not found in repo", force=True)

    def push_fatobjs(self, objects: List[FatObj]):
        if len(objects) == 0:
            self.verbose("git-fat push: nothing to push", force=True)
            return

        for obj in objects:
            self.verbose(f"git-fat push: uploading {obj.path}", force=True)
            self.fatstore.upload(str(self.objdir / obj.fatid))

    def push(self):
        self.setup()
        local_fatfiles = os.listdir(self.objdir)
        remote_fatfiles = self.fatstore.list()
        commited_fatobjs = self.get_fatobjs()

        push_candidates = [fatobj for fatobj in commited_fatobjs if fatobj.fatid in local_fatfiles]
        if len(push_candidates) == 0:
            self.verbose("git-fat push: nothing to push", force=True)
            return

        needs_pushing = [fatobj for fatobj in push_candidates if fatobj.fatid not in remote_fatfiles]
        self.push_fatobjs(needs_pushing)

    def status(self):
        pass
