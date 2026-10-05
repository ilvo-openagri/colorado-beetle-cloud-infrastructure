#!/bin/sh
set -e

# Set alias
until mc alias set myminio http://minio-api-and-console.ilvo-openagri-minio.svc.cluster.local:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD; do
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

# Create drone user
if ! mc admin user info myminio openagri-drone-user > /dev/null 2>&1; then
  echo "Creating user openagri-drone-user..."
  mc admin user add myminio openagri-drone-user "$MINIO_DRONE_USER_PASSWORD"
else
  echo "User openagri-drone-user already exists. Skipping creation."
fi

# Create AI webserver user
if ! mc admin user info myminio openagri-webserver-user > /dev/null 2>&1; then
  echo "Creating user openagri-webserver-user..."
  mc admin user add myminio openagri-webserver-user "$MINIO_WEBSERVER_USER_PASSWORD"
else
  echo "User openagri-webserver-user already exists. Skipping creation."
fi

# Create policy (optional)
if mc admin policy info myminio openagri-drone-policy > /dev/null 2>&1; then
  echo "Policy openagri-drone-policy already exists. Removing this first."
  for USER in openagri-drone-user openagri-webserver-user; do
    if mc admin user info myminio $USER >/dev/null 2>&1; then
      mc admin policy detach myminio openagri-drone-policy --user $USER
      echo "Policy removed for $USER"
    fi
  done
  mc admin policy remove myminio openagri-drone-policy
fi
echo "Creating policy openagri-drone-policy..."
mc admin policy create myminio openagri-drone-policy /config/openagri-policy.json

# Attach policy
echo "Attaching policy openagri-drone-policy to user openagri-drone-user..."
mc admin policy attach myminio openagri-drone-policy --user openagri-drone-user
mc admin policy attach myminio openagri-drone-policy --user openagri-webserver-user

# Create wehbook:

# mc alias set myminio http://localhost:9000 [REDACTED] [REDACTED]123
mc admin config set myminio notify_webhook:drone_img_webhook endpoint=$WEBHOOK_ENDPOINT
mc admin service restart myminio --json
until mc alias set myminio http://minio-api-and-console.ilvo-openagri-minio.svc.cluster.local:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD; do
  echo "Waiting for MinIO to be ready..."
  sleep 2
done

# List existing events on the bucket
EVENTS=$(mc event list myminio/openagri-raw)

case "$EVENTS" in
  *"arn:minio:sqs::drone_img_webhook:webhook"*)
    echo "Event rule already exists for myminio/openagri-raw"
    ;;
  *)
    echo "Adding event rule for myminio/openagri-raw"
    # Add the correct rule
    mc event add myminio/openagri-raw arn:minio:sqs::drone_img_webhook:webhook --event put
    echo "Event rule added"
    ;;
esac
