from git_fat.utils import ConfigParser


def test_is_fatstore_s3(test_s3_git_repo):
    configparser = ConfigParser(test_s3_git_repo.workspace)
    print(configparser.is_fatstore_s3())
