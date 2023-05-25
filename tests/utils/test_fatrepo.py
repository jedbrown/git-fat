from git_fat.utils import FatRepo
from git_fat.fatstores import S3FatStore
from pytest_git import GitRepo
import pytest
import os
import io
import sys
import subprocess


def test_get_indexed_fatobjs(fatrepo):
    all_fatobjs = fatrepo.get_indexed_fatobjs()
    assert len(list(all_fatobjs)) == 2
    expected_fatobjs = ["a.fat", "b.fat"]
    filtered = [fatobj for fatobj in all_fatobjs if fatobj.path not in expected_fatobjs]
    assert len(filtered) == 0


def test_filter_clean(cloned_fatrepo: FatRepo, resource_path):
    fatrepo = cloned_fatrepo
    fatfile = fatrepo.workspace / "a.fat"

    # test to ensure no double cleans
    with open(fatfile, "rb") as in_file, io.BytesIO() as out_file:
        fatrepo.filter_clean(in_file, out_file)
        assert fatfile.read_bytes() == out_file.getvalue()

    expected_sha1_digest = "f17cc23d902436b2c06e682c48e2a4132274c8d0"
    fatrepo.gitapi.git.execute(command=["git-fat", "init"])
    fatfile = resource_path / "cool-ranch.webp"
    with open(fatfile, "rb") as fatstream:
        fatrepo.filter_clean(fatstream, sys.stdout.buffer)

    fatcache = fatrepo.objdir / expected_sha1_digest
    print(f"Expecting following file: {fatcache}")
    assert fatcache.exists()


def test_filter_smudge(fatrepo):
    head = fatrepo.gitapi.head.commit
    fatstub = (head.tree / "a.fat").data_stream

    with io.BytesIO() as buffer:
        fatrepo.filter_smudge(fatstub, buffer)
        fatstub_bytes = buffer.getvalue()
        assert b"fat content a\n" == fatstub_bytes


def test_push(fatrepo, s3_fatstore):
    # nothing to push
    fatrepo.push()

    store_count = len(s3_fatstore.list())
    s3_fatstore.delete("6df0c57803617bba277e90c6fa01071fb6bfebb5")
    fatrepo.push()
    after_push_count = len(s3_fatstore.list())
    assert store_count == after_push_count


def test_pull(fatrepo: FatRepo, cloned_fatrepo: FatRepo):
    # nothing to pull
    fatrepo.pull()

    head = cloned_fatrepo.gitapi.head.commit
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


def test_get_added_fatobjs(s3_gitrepo: GitRepo, fatrepo: FatRepo):
    gitrepo = s3_gitrepo
    gitrepo.run("git checkout -B more_fat")
    c_fat = gitrepo.workspace / "c.fat"
    c_fat.write_text("fat content c")
    gitrepo.run("git add --all")
    gitrepo.run("git commit --no-gpg-sign -m 'adding more fat'")

    new_fatobjs = list(fatrepo.get_added_fatobjs(gitrepo.api.commit("master")))
    assert len(new_fatobjs) == 1
    assert new_fatobjs[0].path == "c.fat"


def test_confirm_on_remote(fatrepo: FatRepo):
    all_fatobjs = fatrepo.get_indexed_fatobjs()
    fatrepo.confirm_on_remote(all_fatobjs)

    # TODO remove one object
    fatrepo.fatstore.delete(list(all_fatobjs)[0].fatid)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        fatrepo.confirm_on_remote(all_fatobjs)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_fatstore_check(fatrepo: FatRepo):
    fatrepo.fatstore_check([])


def test_publish_added_fatobjs(fatrepo: FatRepo, s3_smudgestore: S3FatStore):
    subprocess.run(["git-fat", "init"], cwd=str(fatrepo.workspace), stdout=sys.stdout, stderr=sys.stderr)
    subprocess.run(
        ["git", "checkout", "-B", "more_fat"], cwd=str(fatrepo.workspace), stdout=sys.stdout, stderr=sys.stderr
    )
    e_fat = fatrepo.workspace / "e.fat"
    e_fat.write_text("fat content e")
    test_dir = fatrepo.workspace / "test dir"
    test_dir.mkdir(493)
    f_fat = test_dir / "f.fat"
    f_fat.write_text("fat content f")
    subprocess.run(["git", "add", "--all"], cwd=str(fatrepo.workspace), stdout=sys.stdout, stderr=sys.stderr)

    subprocess.run(
        ["git", "commit", "--no-gpg-sign", "-m", "'adding more fat'"],
        cwd=str(fatrepo.workspace),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    subprocess.run(["git-fat", "push"], cwd=str(fatrepo.workspace), stdout=sys.stdout, stderr=sys.stderr)
    new_fatobj_cache = fatrepo.objdir / "1d76f0a0a53de1d5255240d6aec3a383b700ca98"
    os.remove(str(new_fatobj_cache))

    master = fatrepo.gitapi.commit("master")
    fatrepo.publish_added_fatobjs(master)
    print(s3_smudgestore.list())
