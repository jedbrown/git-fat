from typing import List, Dict
import boto3
import os
from .syncbackend import SyncBackend
from botocore.config import Config


class S3FatStore(SyncBackend):
    def __init__(
        self,
        conf: Dict,
    ):
        self.bucket_name = self.get_bucket_name(conf["bucket"])
        self.prefix = conf.get("perfix")
        self.conf = conf

        self.s3 = self.get_s3_resource()
        self.bucket = self.s3.Bucket(self.bucket_name)

    def get_bucket_name(self, possible_name: str):
        s3_uri_prefix = "s3://"
        if possible_name.startswith(s3_uri_prefix):
            return possible_name[len(s3_uri_prefix) :]
        return possible_name

    def get_s3_resource(self):
        named_args = {}
        if self.conf.get("endpoint"):
            named_args["endpoint_url"] = self.conf.get("endpoint")

        if self.conf.get("id") and self.conf.get("secret"):
            named_args["aws_access_key_id"] = self.conf.get("id")  # pragma: no cover
            named_args["aws_secret_access_key"] = self.conf.get("secret")  # pragma: no cover

        return boto3.resource("s3", config=Config(signature_version="s3v4"), verify=False, **named_args)

    def upload(self, local_filename: str, remote_filename=None) -> None:
        xargs = {}
        if self.conf.get("xpushargs"):
            xargs["ExtraArgs"] = self.conf["xpushargs"]
        if remote_filename is None:
            remote_filename = os.path.basename(local_filename)
        self.bucket.upload_file(Filename=local_filename, Key=remote_filename, **xargs)

    def list(self) -> List[str]:
        remote_files = [item.key for item in self.bucket.objects.all()]
        return remote_files

    def download(self, remote_filename: str, local_filename: os.PathLike) -> None:
        self.bucket.download_file(remote_filename, local_filename)

    def delete(self, filename: str) -> None:
        s3_object = self.bucket.Object(filename)
        s3_object.delete()
