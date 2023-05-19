from git_fat.utils import FatRepo
import io
import sys


def test_is_fatstore_s3(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    assert fatrepo.is_fatstore_s3()


def test_is_fat_file(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    assert fatrepo.is_fatfile(filename=s3_gitrepo.workspace / "a.fat")


def test_get_fatobjs(s3_gitrepo):
    fatrepo = FatRepo(s3_gitrepo.workspace)
    all_fatobjs = fatrepo.get_fatobjs()
    assert len(list(all_fatobjs)) == 2
    expected_fatobjs = ["a.fat", "b.fat"]
    filtered = [fatobj for fatobj in all_fatobjs if fatobj.path not in expected_fatobjs]
    assert len(filtered) == 0


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
        assert b"fat content a\n" == fatstub_bytes


def test_push(s3_gitrepo, s3_fatstore):
    gitrepo = s3_gitrepo
    fatrepo = FatRepo(gitrepo.workspace)
    # nothing to push
    fatrepo.push()

    s3_fatstore.delete("6df0c57803617bba277e90c6fa01071fb6bfebb5")
    assert len(s3_fatstore.list()) == 2
    fatrepo.push()
    assert len(s3_fatstore.list()) == 3


def test_pull(s3_gitrepo, s3_cloned_gitrepo):
    gitrepo = s3_gitrepo
    fatrepo = FatRepo(gitrepo.workspace)
    # nothing to pull
    fatrepo.pull()

    cloned_fatrepo = FatRepo(s3_cloned_gitrepo.workspace)
    head = s3_cloned_gitrepo.api.head.commit
    a_fat = (head.tree / "a.fat").data_stream
    print(f"fatstub : {a_fat.read()}")

    cloned_fatrepo.gitapi.git.execute(
        command=["git", "fat", "init"],
        stdout_as_string=True,
    )
    a_fat_path = cloned_fatrepo.workspace / "a.fat"
    cloned_fatrepo.pull(files=[a_fat_path])
    with open(cloned_fatrepo.workspace / "a.fat") as fd:
        print("Reading content of restored a.fat file:")
        print(fd.read())

    cloned_fatrepo.pull_all()

    status = cloned_fatrepo.gitapi.git.execute(
        command=["git", "status"],
        stdout_as_string=True,
    )
    print(f"comfirming no changes:\n {status}")
    with open(cloned_fatrepo.workspace / "b.fat") as fd:
        print("Reading content of restored b.fat file:")
        print(fd.read())

    status = cloned_fatrepo.gitapi.git.execute(
        command=["git", "status"],
        stdout_as_string=True,
    )
    print(f"comfirming no changes:\n {status}")
