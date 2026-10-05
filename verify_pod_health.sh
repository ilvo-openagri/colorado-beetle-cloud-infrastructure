#!/bin/bash

echo "=== Checking pod status ==="
microk8s kubectl get pods -A

echo
echo "=== Checking for ImagePullBackOff or ErrImagePull ==="
microk8s kubectl get pods -A | grep -E "ImagePullBackOff|ErrImagePull" || echo "No image pull errors found"

echo
echo "=== Checking for CrashLoopBackOff ==="
microk8s kubectl get pods -A | grep CrashLoopBackOff || echo "No CrashLoopBackOff pods"

echo
echo "=== Checking imagePullPolicy settings ==="
microk8s kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{.spec.containers[*].imagePullPolicy}{"\n"}{end}' \
  | sort -u

echo
echo "=== Listing all images referenced by pods ==="
microk8s kubectl get pods -A \
  -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' \
  | sort -u > /tmp/pod-images.txt
cat /tmp/pod-images.txt

echo
echo "=== Checking if all referenced images exist in containerd ==="
missing=0
for img in $(cat /tmp/pod-images.txt); do
    if [[ "$img" == *@sha256:* ]]; then
        digest="${img##*@}"
        match=$(microk8s ctr images ls -q | grep "$digest" || true)
    else
        repo=$(echo "$img" | cut -d: -f1)
        tag=$(echo "$img" | cut -d: -f2)
        match=$(microk8s ctr images ls -q | grep "$repo" | grep "$tag" || true)
    fi

    if [ -z "$match" ]; then
        echo "MISSING: $img"
        missing=1
    fi
done

if [ $missing -eq 0 ]; then
    echo "All images are present in containerd"
else
    echo "Some images are missing in containerd"
fi

echo
echo "=== Final cluster health summary ==="
if microk8s kubectl get pods -A | grep -qE "ImagePullBackOff|ErrImagePull|CrashLoopBackOff"; then
    echo "❌ Cluster NOT fully healthy"
else
    echo "✅ Cluster healthy and fully offline-ready"
fi
