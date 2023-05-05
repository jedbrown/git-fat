from git.repo import Repo
from pathlib import Path
import configparser as iniparser


class ConfigParser:
    def __init__(self, directory: str):
        self.repo = Repo(directory)
        self.workspace = Path(directory)
        self.gitfat_config_path = self.workspace / ".gitfat"
        self.gitfat_config = self.get_gitfat_config()

    def get_gitfat_config(self):
        gitfat_config = iniparser.ConfigParser()
        gitfat_config.read(self.gitfat_config_path)

        if len(gitfat_config.sections()) != 1:
            raise Exception("Invalid gitfat config")

        return gitfat_config

    def is_fatstore_s3(self):
        return "s3" in self.gitfat_config.sections()
