from git_fat.utils import FatRepo
import io
import sys
import os


def test_is_fatstore_s3(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    assert fatrepo.is_fatstore_s3()


def test_is_fat_file(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    assert fatrepo.is_fatfile(filename=s3_gitrepo.workspace / "a.fat")


def test_get_fatobjs(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    blobs = fatrepo.get_fatobjs()
    paths = [blob.path for blob in blobs]
    assert len(list(blobs)) == 2
    assert paths.sort() == ["a.fat", "b.fat"].sort()


def test_filter_clean(s3_cloned_gitrepo, resource_path):
    gitrepo = s3_cloned_gitrepo
    workspace = gitrepo.workspace
    fatrepo = FatRepo(gitrepo.workspace)
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


def test_filter_smudge(s3_gitrepo):
    gitrepo = s3_gitrepo
    fatrepo = FatRepo(gitrepo.workspace)

    head = gitrepo.api.head.commit
    fatstub = (head.tree / "a.fat").data_stream

    with io.BytesIO() as buffer:
        fatrepo.filter_smudge(fatstub, buffer)
        fatstub_bytes = buffer.getvalue()
        assert b'fat content a\n' == fatstub_bytes


def test_push(s3_gitrepo, s3_fatstore):
    gitrepo = s3_gitrepo
    os.listdir(gitrepo.workspace / ".git/fat/objects")
    fatrepo = FatRepo(gitrepo.workspace)
    # nothing to push
    fatrepo.push()

    s3_fatstore.delete('6df0c57803617bba277e90c6fa01071fb6bfebb5')
    assert len(s3_fatstore.list()) == 2
    fatrepo.push()
    assert len(s3_fatstore.list()) == 3
