def test_git_fat_repo(s3_gitrepo):
    a_fat = (s3_gitrepo.workspace / "a.fat").read_text()
    assert a_fat == "fat content a\n"


def test_git_fat_push(s3_gitrepo):
    s3_gitrepo.run("gfat push")


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


# def test_gfat_pull(s3_cloned_gitrepo):
#     s3_cloned_gitrepo.run("git fat init")
#     content_before_pull = (s3_cloned_gitrepo.workspace / "a.fat").read_text()
#     s3_cloned_gitrepo.run("gfat pull a.fat")
#     content = (s3_cloned_gitrepo.workspace / "a.fat").read_text()
#     assert content_before_pull != "fat content a\n"
#     assert content == "fat content a\n"
#
#     # pull all files
#     s3_cloned_gitrepo.run("gfat pull -a")
