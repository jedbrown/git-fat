from git_fat.utils import FatRepo


def test_is_fatstore_s3(test_s3_git_repo):
    fatrepo = FatRepo(test_s3_git_repo.workspace)
    assert fatrepo.is_fatstore_s3()


def test_is_fat_file(test_s3_git_repo):
    fatrepo = FatRepo(test_s3_git_repo.workspace)
    assert fatrepo.is_fat_file(filename=test_s3_git_repo.workspace / "a.fat")


def test_get_fat_objects(test_s3_git_repo):
    fatrepo = FatRepo(test_s3_git_repo.workspace)
    blobs = fatrepo.get_fat_objects()
    paths = [blob.path for blob in blobs]
    assert len(list(blobs)) == 2
    assert paths.sort() == ["a.fat", "b.fat"].sort()
