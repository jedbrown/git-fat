import os
import io
import sys
import types
import pytest


def test_git_fat_repo(s3_gitrepo):
    a_fat = (s3_gitrepo.workspace / "a.fat").read_text()
    assert a_fat == "fat content a\n"


def test_git_fat_push(s3_gitrepo):
    s3_gitrepo.run("git fat push")


def test_git_fat_filter_clean(s3_cloned_gitrepo):
    content = (s3_cloned_gitrepo.workspace / "a.fat").read_text()
    assert content != "fat content a\n"


def test_git_fat_pull(s3_cloned_gitrepo):
    s3_cloned_gitrepo.run("git fat init")
    content_before_pull = (s3_cloned_gitrepo.workspace / "a.fat").read_text()
    print(content_before_pull)
    s3_cloned_gitrepo.run("git fat pull a.fat")
    content = (s3_cloned_gitrepo.workspace / "a.fat").read_text()
    print(content)
    assert content_before_pull != "fat content a\n"
    assert content == "fat content a\n"

    # pull all files
    s3_cloned_gitrepo.run("git fat pull --all")


def test_versions(s3_gitrepo):
    s3_gitrepo.run("git fat -v")


def test_get_gitroot():
    from git_fat.cmdline import get_gitroot, NotInGitrepo

    get_gitroot()
    os.chdir("/tmp")
    with pytest.raises(NotInGitrepo):
        get_gitroot()


def test_get_fatrepo(s3_gitrepo):
    os.chdir(s3_gitrepo.workspace)
    from git_fat.cmdline import get_fatrepo

    get_fatrepo()


def test_get_valid_fpaths(s3_gitrepo):
    from git_fat.cmdline import get_valid_fpaths

    paths = ["a.fat", "b.fat", "c.fat"]
    os.chdir(s3_gitrepo.workspace)
    get_valid_fpaths(paths)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        get_valid_fpaths([])
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_fatstore_check_cmd(s3_gitrepo):
    s3_gitrepo.run("git-fat fscheck")
    s3_gitrepo.run("git-fat fscheck a.fat")
    s3_gitrepo.run("git-fat fscheck-new")


def test_cmdline_main(s3_gitrepo, monkeypatch):
    from git_fat.cmdline import main

    os.chdir(s3_gitrepo.workspace)
    with pytest.raises(SystemExit) as pytest_wrapped_e, monkeypatch.context() as m:
        m.setattr(sys, "argv", ["git-fat"])
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_cmdline_pull_cmd():
    from git_fat.cmdline import pull_cmd

    args = types.SimpleNamespace()
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        pull_cmd(args)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_cmdline_filter_smudge(monkeypatch, s3_gitrepo):
    monkeypatch.setattr("sys.stdin", io.BytesIO(b"fat content a"))
    s3_gitrepo.run("git-fat filter-smudge")
