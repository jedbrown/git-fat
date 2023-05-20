def test_upload_file(wait_for_s3, workspace, s3_fatstore):
    test_file = workspace.workspace / "test.txt"
    test_file.write_text("Hello World\n")
    s3_fatstore.upload(test_file.abspath())


def test_list(wait_for_s3, s3_fatstore):
    files = s3_fatstore.list()
    print(files)
    assert len(files) >= 1


def test_download_file(wait_for_s3, workspace, s3_fatstore):
    filename = "test.txt"
    file_fullpath = workspace.workspace / filename
    s3_fatstore.download(filename, file_fullpath)
    content = file_fullpath.read_text()
    assert content == "Hello World\n"
