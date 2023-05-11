from git_fat.utils import FatRepo
import hashlib
import io


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


def test_filter_clean(s3_cloned_gitrepo):
    gitrepo = s3_cloned_gitrepo
    workspace = gitrepo.workspace
    fatrepo = FatRepo(s3_cloned_gitrepo.workspace)
    fatfile = workspace / "a.fat"

    with open(fatfile, "r") as in_file, io.StringIO() as out_file:
        fatrepo.filter_clean(in_file, out_file)
        assert fatfile.read_text() == out_file.getvalue()

    content = b"fat content test"
    test_file = workspace / "test.fat"
    test_file.write_text(content.decode())
    test_file_sha1_digest = hashlib.sha1(content).hexdigest()
    gitrepo.run("git fat init")
    gitrepo.run("git add --all")
    gitrepo.api.index.commit("Adding test fat")
    fatobj = (fatrepo.objdir / test_file_sha1_digest)
    assert fatobj.exists()
