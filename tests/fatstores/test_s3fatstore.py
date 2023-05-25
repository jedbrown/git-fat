from git_fat.fatstores import S3FatStore
import tomli


def test_upload_file(workspace, s3_fatstore):
    test_file = workspace.workspace / "test.txt"
    test_file.write_text("Hello World\n")
    s3_fatstore.upload(test_file.abspath())


def test_list(s3_fatstore):
    files = s3_fatstore.list()
    print(files)
    assert len(files) >= 1


def test_download_file(workspace, s3_fatstore):
    filename = "test.txt"
    file_fullpath = workspace.workspace / filename
    s3_fatstore.download(filename, file_fullpath)
    content = file_fullpath.read_text()
    assert content == "Hello World\n"


def test_get_bucket_name():
    sampleconf = """
    [s3]
    bucket = 'munkirepo'
    endpoint = 'http://127.0.0.1:9000'
    [s3.extrapushargs]
    ACL = 'bucket-owner-full-control'
    """
    config = tomli.loads(sampleconf)
    fatstore = S3FatStore(config["s3"])
    assert fatstore.get_bucket_name("munkirepo") == "munkirepo"


def test_delete(s3_fatstore):
    s3_fatstore.delete("test.txt")
