import pytest
from pytest_shutil.cmdline import copy_files
from pytest_shutil.workspace import Workspace
from git.repo import Repo
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

pytest_plugins = ["docker_compose"]


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
def test_s3_git_repo(git_repo, resource_path_root):
    path = git_repo.workspace
    s3_test_resources = resource_path_root / "s3"
    copy_files(str(s3_test_resources), str(path))
    git_fat_conf = path / ".gitfat"
    conf = """
[s3]
bucket = http://localhost:9000
prefix = munki_repo
extrapushargs = --acl bucket-owner-full-control"""
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


# Invoking this fixture: 'function_scoped_container_getter' starts all services
@pytest.fixture(scope="session")
def wait_for_s3(session_scoped_container_getter):
    """Wait for the api from my_api_service to become responsive"""
    request_session = requests.Session()
    retries = Retry(total=10, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
    request_session.mount("http://", HTTPAdapter(max_retries=retries))

    service = session_scoped_container_getter.get("minio").network_info[0]
    api_url = "http://%s:%s/minio/health/live" % ("127.0.0.1", service.host_port)
    assert request_session.get(api_url)
    return request_session, api_url
