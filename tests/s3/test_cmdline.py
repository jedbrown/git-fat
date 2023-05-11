def test_git_fat_repo(s3_gitrepo):
    a_fat = (s3_gitrepo.workspace / "a.fat").read_text()
    assert a_fat == "fat content a\n"


def test_git_fat_push(wait_for_s3, s3_gitrepo):
    s3_gitrepo.run("git fat push")


def test_git_fat_filter_clean(s3_gitrepo_clone):
    content = (s3_gitrepo_clone.workspace / "a.fat").read_text()
    assert content != "fat content a\n"


def test_git_fat_pull(wait_for_s3, s3_gitrepo_clone):
    s3_gitrepo_clone.run("git fat init")
    content_before_pull = (s3_gitrepo_clone.workspace / "a.fat").read_text()
    s3_gitrepo_clone.run("git fat pull")
    content = (s3_gitrepo_clone.workspace / "a.fat").read_text()
    assert content_before_pull != "fat content a\n"
    assert content == "fat content a\n"
