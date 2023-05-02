def test_git_fat_repo(test_s3_git_repo):
    a_fat = (test_s3_git_repo.workspace / 'a.fat').read_text()
    assert a_fat == "fat content a\n"
