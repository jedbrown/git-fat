def test_upload_file(wait_for_s3, workspace, s3_fatstore):
    test_file = (workspace.workspace / "test.txt")
    test_file.write_text("Hello World\n")
    s3_fatstore.upload(test_file.abspath())
