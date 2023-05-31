from typing import List, Dict
import boto3
import os
from .syncbackend import SyncBackend
from botocore.config import Config
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings


def get_predictable_prefix(prefix: str):
    if not prefix:
        return prefix
    if prefix.endswith("/"):
        return prefix
    else:
        return prefix + "/"


def get_bucket_name(possible_name: str):
    s3_uri_prefix = "s3://"
    if possible_name.startswith(s3_uri_prefix):
        return possible_name[len(s3_uri_prefix) :]
    return possible_name


class S3FatStore(SyncBackend):
    def __init__(
        self,
        conf: Dict,
    ):
        self.bucket_name = get_bucket_name(conf["bucket"])
        self.prefix = get_predictable_prefix(conf.get("prefix", ""))
        self.conf = conf

        self.s3 = self.get_s3_resource()
        self.bucket = self.s3.Bucket(self.bucket_name)
        disable_warnings(InsecureRequestWarning)

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
        if self.prefix:
            remote_filename = os.path.join(self.prefix, remote_filename)
        self.bucket.upload_file(Filename=local_filename, Key=remote_filename, **xargs)

    def strip_prefix(self, identifier):
        if identifier.startswith(self.prefix) and self.prefix:
            return identifier[len(self.prefix) :]
        return identifier

    def list(self) -> List[str]:
        if self.prefix:
            remote_objs = self.bucket.objects.filter(Prefix=self.prefix).all()
        else:
            remote_objs = self.bucket.objects.all()
        remote_files = [self.strip_prefix(item.key) for item in remote_objs]
        return remote_files

    def download(self, remote_filename: str, local_filename: os.PathLike) -> None:
        if self.prefix:
            remote_filename = os.path.join(self.prefix, remote_filename)
        self.bucket.download_file(remote_filename, local_filename)

    def delete(self, filename: str) -> None:
        if self.prefix:
            remote_fname = os.path.join(self.prefix, filename)
        else:
            remote_fname = filename
        s3_object = self.bucket.Object(remote_fname)
        s3_object.delete()
