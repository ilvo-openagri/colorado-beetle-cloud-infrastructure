import boto3
import logging
from multiprocessing import Process, Queue


class MinioController:
    """
    MinioController is a class that manages the interaction with a MinIO server.
    """

    def __init__(self, minio_url: str, access_key: str, secret_key: str):
        self._minio_url = minio_url
        self._access_key = access_key
        self._secret_key = secret_key
        self.logger = logging.getLogger(__name__)

        self._s3_client = boto3.client(
            "s3",
            endpoint_url=minio_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            use_ssl=False,
            verify=False,
        )

    def delete_file(self, bucket_name: str, object_name: str, recursive: bool = False):
        """
        Deletes a file/directory from the MinIO server.

        Args:
            bucket_name (str): The name of the target bucket.
            object_name (str): The name of the object in the bucket.
            recursive (bool): If True, delete all objects in the directory.
        """
        if recursive:
            # 1. List all objects with that prefix
            response = self._s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=object_name
            )

            # 2. Batch delete all found objects
            if "Contents" in response:
                objects_to_delete = [
                    {"Key": obj["Key"]} for obj in response["Contents"]
                ]
                self._s3_client.delete_objects(
                    Bucket=bucket_name, Delete={"Objects": objects_to_delete}
                )
                print(f"Deleted {len(objects_to_delete)} objects")
            else:
                print("No objects found to delete.")
        else:
            self._s3_client.delete_object(
                Bucket=bucket_name,
                Key=object_name,
            )
