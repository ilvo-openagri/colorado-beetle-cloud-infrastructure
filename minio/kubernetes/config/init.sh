#!/bin/sh
set -ex

# Set alias
until mc alias set myminio http://minio-api-and-console.ilvo-minio.svc.cluster.local:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD; do
  echo "Waiting for MinIO to be ready..."
  sleep 2
done

# Create buckets
# 1. Raw images
if ! mc ls myminio/openagri-raw > /dev/null 2>&1; then
  echo "Bucket openagri-raw does not exist. Creating it..."
    mc mb myminio/openagri-raw
else
  echo "Bucket openagri-raw already exists. Skipping creation."
fi


if ! mc ls myminio/openagri-detection > /dev/null 2>&1; then
  echo "Bucket openagri-detection does not exist. Creating it..."
    mc mb myminio/openagri-detection
else
  echo "Bucket openagri-detection already exists. Skipping creation."
fi

# Create users
if ! mc admin user info myminio openagri-drone-user > /dev/null 2>&1; then
  echo "Creating user openagri-drone-user..."
  mc admin user add myminio openagri-drone-user [REDACTED]
else
  echo "User openagri-drone-user already exists. Skipping creation."
fi

# Create policy (optional)
if ! mc admin policy info myminio openagri-drone-policy > /dev/null 2>&1; then
  echo "Creating policy openagri-drone-policy..."
  mc admin policy create myminio openagri-drone-policy /config/openagri-policy.json
else
  echo "Policy openagri-drone-policy already exists. Skipping creation."
fi

# Attach policy
echo "Attaching policy openagri-drone-policy to user openagri-drone-user..."
mc admin policy attach myminio openagri-drone-policy --user openagri-drone-user

