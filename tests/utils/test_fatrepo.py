from git_fat.utils import FatRepo
import io


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


def test_filter_clean(test_s3_git_repo_clone):
    fatrepo = FatRepo(test_s3_git_repo_clone.workspace)
    fatfile = test_s3_git_repo_clone.workspace / "a.fat"
    with open(fatfile, "r") as in_file, io.StringIO() as out_file:
        fatrepo.filter_clean(in_file, out_file)
        assert fatfile.read_text() == out_file.getvalue()
