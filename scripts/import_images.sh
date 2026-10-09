set -euo pipefail
shopt -s nullglob

for f in exported/*.tar; do
  echo "Importing $f"
  microk8s ctr images import "$f"
done
