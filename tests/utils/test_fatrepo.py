from git_fat.utils import FatRepo
import io
import sys


def test_is_fatstore_s3(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    assert fatrepo.is_fatstore_s3()


def test_is_fat_file(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    assert fatrepo.is_fatfile(filename=s3_gitrepo.workspace / "a.fat")


def test_get_fatobj(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    blobs = fatrepo.get_fatobj()
    paths = [blob.path for blob in blobs]
    assert len(list(blobs)) == 2
    assert paths.sort() == ["a.fat", "b.fat"].sort()


def test_filter_clean(s3_cloned_gitrepo, resource_path):
    gitrepo = s3_cloned_gitrepo
    workspace = gitrepo.workspace
    fatrepo = FatRepo(s3_cloned_gitrepo.workspace)
    fatfile = workspace / "a.fat"

    with open(fatfile, "r") as in_file, io.StringIO() as out_file:
        fatrepo.filter_clean(in_file, out_file)
        assert fatfile.read_text() == out_file.getvalue()

    expected_sha1_digest = "f17cc23d902436b2c06e682c48e2a4132274c8d0"
    gitrepo.run("git fat init")
    fatfile = resource_path / "cool-ranch.webp"
    with open(fatfile, "rb") as fatstream:
        fatrepo.filter_clean(fatstream, sys.stdout.buffer)

    assert (fatrepo.objdir / expected_sha1_digest).exists()
