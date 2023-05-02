import pytest
from pytest_shutil.cmdline import copy_files
from pytest_shutil.workspace import Workspace
from git.repo import Repo


class ClonedGitRepo(Workspace):
    """
    Clones a Git repository in a temporary workspace.
    Cleans up on exit.
    Attributes
    ----------
    uri : `str`
        repository base uri
    api : `git.Repo` handle to the repository
    """

    def __init__(self, source):
        super(ClonedGitRepo, self).__init__()
        self.api = Repo.clone_from(url=source, to_path=self.workspace)
        self.uri = "file://%s" % self.workspace


@pytest.fixture(scope="session")
def rsync_dest_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("data")


@pytest.fixture()
def test_s3_git_repo(git_repo, resource_path_root, rsync_dest_dir):
    path = git_repo.workspace
    s3_test_resources = resource_path_root / "s3"
    copy_files(str(s3_test_resources), str(path))
    git_fat_conf = path / ".gitfat"
    conf = f"""
    [rsync]
    remote = {rsync_dest_dir}
    """
    git_fat_conf.write_text(conf)
    git_repo.run("git fat init")
    git_repo.run("git add --all")
    git_repo.api.index.commit("Initial commit")
    print(git_repo.workspace)
    return git_repo


@pytest.fixture()
def test_s3_git_repo_clone(test_s3_git_repo):
    repo = ClonedGitRepo(test_s3_git_repo.workspace)
    return repo
