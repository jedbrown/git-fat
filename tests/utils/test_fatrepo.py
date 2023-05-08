from git_fat.utils import FatRepo


def test_is_fatstore_s3(test_s3_git_repo):
    fatrepo = FatRepo(test_s3_git_repo.workspace)
    assert fatrepo.is_fatstore_s3()


def test_is_fat_file(test_s3_git_repo):
    fatrepo = FatRepo(test_s3_git_repo.workspace)
    assert fatrepo.is_fat_file(filename=test_s3_git_repo.workspace / "a.fat")
