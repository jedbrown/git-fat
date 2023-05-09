from git.repo import Repo
import git.objects
from pathlib import Path
from hashlib import sha1
from typing import Union, List, Set, Tuple
import configparser as iniparser


class FatRepo:
    def __init__(self, directory: str):
        self.gitapi = Repo(directory)
        self.workspace = Path(directory)
        self.gitfat_config_path = self.workspace / ".gitfat"
        self.gitfat_config = self.get_gitfat_config()
        self.magiclen = self.get_magiclen()
        self.cookie = "#$# git-fat"

    def encode_fat_stub(self, digest: str, size: float) -> str:
        """
        Returns a string containg the git-fat stub of a file cleaned with the git-fat filter.
        I.E. #$# git-fat file_hex_digest file_size
            Parameters:
                digest (str): SHA1 Sum of file
                size (float): Size of file in bytes
        """
        return "#$# git-fat %s %20d\n" % (digest, size)

    def get_magiclen(self) -> int:
        dummy_file_contents = b"dummy"
        dummy_file_sha1 = sha1(b"dummy").hexdigest()
        dummy_file_size = len(dummy_file_contents)
        return len(self.encode_fat_stub(dummy_file_sha1, dummy_file_size))

    def decode_fat_stub(self, string: str) -> Tuple[str, Union[int, None]]:
        """
        Returns the SHA1 hex digest and size of a file that's been smudged by the git-fat filter
            Parameters:
                string: Git fat stub string
        """

        parts = string[len(self.cookie):].split()
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

    def is_fat_file(self, filename: str):
        file_filters = self.gitapi.git.execute(
            command=["git", "check-attr", "filter", "--", filename],
            stdout_as_string=True,
        )
        return "filter: fat" in str(file_filters)

    def is_gitfat_blob(self, item):
        if item.type != "blob":
            return False

        if item.size != self.magiclen:
            return False

        return item.data_stream.read().decode().startswith(self.cookie)

    def get_all_git_references(self) -> List[str]:
        return [str(ref) for ref in self.gitapi.refs]

    def get_fat_objects(
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
                item
                for item in commit.tree.traverse()
                if self.is_gitfat_blob(item)
            )
            objects.update(fat_blobs)
        return objects

    def status(self):
        pass
