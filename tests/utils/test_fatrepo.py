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
    blobs = fatrepo.get_fatobjs()
    paths = [blob.path for blob in blobs]
    assert len(list(blobs)) == 2
    assert paths.sort() == ["a.fat", "b.fat"].sort()


def test_filter_clean(s3_cloned_gitrepo, resource_path):
    gitrepo = s3_cloned_gitrepo
    workspace = gitrepo.workspace
    fatrepo = FatRepo(s3_cloned_gitrepo.workspace)
    fatfile = workspace / "a.fat"

    # test to ensure no double cleans
    with open(fatfile, "rb") as in_file, io.BytesIO() as out_file:
        fatrepo.filter_clean(in_file, out_file)
        assert fatfile.read_bytes() == out_file.getvalue()

    expected_sha1_digest = "f17cc23d902436b2c06e682c48e2a4132274c8d0"
    gitrepo.run("git fat init")
    fatfile = resource_path / "cool-ranch.webp"
    with open(fatfile, "rb") as fatstream:
        fatrepo.filter_clean(fatstream, sys.stdout.buffer)

    fatcache = fatrepo.objdir / expected_sha1_digest
    print(f"Expecting following file: {fatcache}")
    assert fatcache.exists()


def test_filter_smudge(s3_cloned_gitrepo):
    gitrepo = s3_cloned_gitrepo
    workspace = gitrepo.workspace
    fatrepo = FatRepo(s3_cloned_gitrepo.workspace)
    fatstub_file = workspace / "a.fat"
    cached_obj_digest = "6df0c57803617bba277e90c6fa01071fb6bfebb5"

    ## pull fat here

    restored_fat = (workspace / "restored.fat")
    with open(fatstub_file, "rb") as in_file, restored_fat.open("wb") as out_file:
        fatrepo.filter_smudge(in_file, out_file)

    restored_text = restored_fat.read_text()
    print(restored_text)
