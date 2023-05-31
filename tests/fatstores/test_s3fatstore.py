def test_upload_file(workspace, s3_fatstore):
    test_file = workspace.workspace / "test.txt"
    test_file.write_text("Hello World\n")
    s3_fatstore.upload(test_file.abspath())


def test_list(s3_fatstore):
    files = s3_fatstore.list()
    print(files)
    assert len(files) >= 1


def test_upload_file_with_prefix(workspace, s3_fatstore_with_prefix):
    test_file = workspace.workspace / "test.txt"
    test_file.write_text("Hello World\n")
    s3_fatstore_with_prefix.upload(test_file.abspath())


def test_list_with_prefix(s3_fatstore_with_prefix):
    files = s3_fatstore_with_prefix.list()
    print(files)
    assert len(files) >= 1


def test_download_file(workspace, s3_fatstore):
    filename = "test.txt"
    file_fullpath = workspace.workspace / filename
    s3_fatstore.download(filename, file_fullpath)
    content = file_fullpath.read_text()
    assert content == "Hello World\n"


def test_get_bucket_name():
    from git_fat.fatstores.s3fatstore import get_bucket_name

    assert get_bucket_name("munkirepo") == "munkirepo"
    assert get_bucket_name("s3://munkirepo") == "munkirepo"


def test_delete(s3_fatstore):
    s3_fatstore.delete("test.txt")
