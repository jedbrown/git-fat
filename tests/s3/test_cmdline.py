def test_git_fat_repo(test_s3_git_repo):
    a_fat = (test_s3_git_repo.workspace / "a.fat").read_text()
    assert a_fat == "fat content a\n"


def test_git_fat_push(wait_for_s3, test_s3_git_repo):
    test_s3_git_repo.run("git fat push")


def test_git_fat_filter_clean(test_s3_git_repo_clone):
    content = (test_s3_git_repo_clone.workspace / "a.fat").read_text()
    assert content != "fat content a\n"


def test_git_fat_pull(wait_for_s3, test_s3_git_repo_clone):
    test_s3_git_repo_clone.run("git fat init")
    content_before_pull = (test_s3_git_repo_clone.workspace / "a.fat").read_text()
    test_s3_git_repo_clone.run("git fat pull")
    content = (test_s3_git_repo_clone.workspace / "a.fat").read_text()
    assert content_before_pull != "fat content a\n"
    assert content == "fat content a\n"
