#!/bin/bash
set -e

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pod_images="$script_dir/pod-images.txt"

mkdir -p exported

# Get images used by pods
microk8s kubectl get pods -A \
  -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' \
    | sort -u > "$pod_images"

ctr_images=$(microk8s ctr images ls -q)

while IFS= read -r img || [[ -n "$img" ]]; do
    echo "Processing $img"

    # If digest is present, match only that digest
    if [[ "$img" == *@sha256:* ]]; then
        digest="${img##*@}"
        match=$(echo "$ctr_images" | grep "$digest" || true)
    else
        # Extract repo and tag
        repo=$(echo "$img" | cut -d: -f1)
        tag=$(echo "$img" | cut -d: -f2)

        # Try matching with registry prefixes
        match=$(echo "$ctr_images" | grep "$repo" | grep "$tag" || true)
    fi

    if [ -z "$match" ]; then
        echo "WARNING: No containerd match for $img"
        continue
    fi

    # If multiple matches, pick the first
    match=$(echo "$match" | head -n1)

    safe=$(echo "$match" | tr '/:@' '_')
    out="exported/${safe}.tar"

    echo "Exporting $match → $out"
    microk8s ctr images export "$out" "$match"
done < "$pod_images"
