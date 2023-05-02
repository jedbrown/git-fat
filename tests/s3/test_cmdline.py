def test_git_fat_repo(test_s3_git_repo):
    a_fat = (test_s3_git_repo.workspace / 'a.fat').read_text()
    assert a_fat == "fat content a\n"


def test_git_clone(test_s3_git_repo_clone):
    content = (test_s3_git_repo_clone.workspace / 'a.fat').read_text()
    print(content)
    assert content != "fat content a\n"
