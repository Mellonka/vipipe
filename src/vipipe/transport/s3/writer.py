from dataclasses import dataclass, field

import botocore.session
from vipipe.transport.interface import WriterABC


@dataclass
class S3WriterConfig:
    bucket_name: str
    """Название S3 бакета"""

    region_name: str
    """Регион S3"""

    access_key: str
    """Ключ доступа к AWS"""

    secret_key: str
    """Секретный ключ доступа к AWS"""

    multipart_threshold: int = 8 * 1024 * 1024
    """Порог для многочастевой загрузки (в байтах)"""


@dataclass
class S3Object:
    key: str
    """Ключ в S3"""

    message: bytes
    """Сообщение"""


@dataclass
class S3Writer(WriterABC[S3Object]):
    config: S3WriterConfig

    session: botocore.session.Session = field(init=False)
    s3_client: botocore.client.BaseClient = field(init=False)  # type: ignore

    def __post_init__(self):
        self.session = botocore.session.get_session()
        self.s3_client = self.session.create_client(
            "s3",
            region_name=self.config.region_name,
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
        )

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def write(self, message: S3Object) -> None:
        if len(message.message) < self.config.multipart_threshold:
            self.s3_client.put_object(Bucket=self.config.bucket_name, Key=message.key, Body=message.message)
        else:
            self._write_message_multipart(message)

    def _write_message_multipart(self, message: S3Object) -> None:
        response = self.s3_client.create_multipart_upload(Bucket=self.config.bucket_name, Key=message.key)
        upload_id = response["UploadId"]

        try:
            parts = []
            for i, part in enumerate(message.message):
                part_response = self.s3_client.upload_part(
                    Bucket=self.config.bucket_name,
                    Key=message.key,
                    PartNumber=i + 1,
                    UploadId=upload_id,
                    Body=part,
                )
                parts.append({"PartNumber": i + 1, "ETag": part_response["ETag"]})

            # Complete multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=message.key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception as e:
            self.s3_client.abort_multipart_upload(Bucket=self.config.bucket_name, Key=message.key, UploadId=upload_id)
            raise e
