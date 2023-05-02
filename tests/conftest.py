import pytest
from pytest_shutil.cmdline import copy_files


@pytest.fixture()
def test_s3_git_repo(git_repo, resource_path_root):
    path = git_repo.workspace
    s3_test_resources = resource_path_root / "s3"
    copy_files(str(s3_test_resources), str(path))
    git_repo.run("git add --all")
    git_repo.api.index.commit("Initial commit")
    return git_repo
