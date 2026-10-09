# OpenAgri Cloud Infrastructure Installation

This guide describes installing the services in this repository on a Linux host running Kubernetes. It expands the deployment notes in [README.md](README.md) into an end-to-end sequence.

The manifests were written for a single-node MicroK8s installation. Kubernetes resources use a Kustomize base and an environment overlay; review the configuration section before applying them to another machine. These manifests configure HTTP ingress; TLS, backups, and production hardening are deployment-specific and are not configured here.

## Prerequisites

- A Linux host with MicroK8s (or a compatible Kubernetes cluster) running and a working `kubectl` context.
- Helm 3 for ingress-nginx, InfluxDB, and Telegraf.
- Docker or another OCI image builder and access to a container registry, if rebuilding Streamlit.
- DNS records for the configured ingress hostnames, pointed at the ingress host or load balancer.
- Persistent storage configured for the cluster, plus the host directories required by the `hostPath` volumes below.

From the repository root, confirm the cluster is reachable:

```bash
kubectl get nodes
helm version
```

For MicroK8s, enable the required Kubernetes features and use its kubectl/Helm commands if they are not exposed on your `PATH`.

## Review Configuration

Do this before deploying anything:

1. Copy `deploy/overlays/ilvo/` to `deploy/overlays/<environment>/` and edit the `deployment-settings` literals in its `kustomization.yaml`. Set ingress DNS names, the MinIO node name, and the PostgreSQL, MinIO, and Streamlit host paths there; do not edit the base manifests. The `ilvo` overlay contains the current site's values as a starting point.
2. Create the configured host directories on the Kubernetes node and ensure the pods can write to their mounted storage. The MinIO setup files are bundled into a ConfigMap, so they no longer require a host mount from the repository checkout.
3. Create local credential files from the `.example` files described below and replace every placeholder. These real files are ignored by Git; do not force-add them.
4. Rotate any credentials that have been used in an earlier deployment or published commit. Removing a file from the latest commit does not invalidate its credentials.
5. Configure InfluxDB and Telegraf with the correct organization, bucket, endpoint, and API tokens. Keep tokens in the ignored local Telegraf configuration files.
6. Streamlit credentials are loaded from the mounted local `.env` file at runtime. The Dockerfile does not copy `.env` into the image.

The overlay is the single source for environment-specific Kubernetes hostnames, node selection, and storage paths. Deploy it with `kubectl apply -k deploy/overlays/<environment>` after preparing the required namespaces, credentials, and host-mounted application configuration below.

## Install Ingress

Install the NGINX ingress controller:

```bash
helm upgrade --install ingress-nginx ingress-nginx \
  --repo https://kubernetes.github.io/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  -f ingress/config.yaml
```

Wait for the controller to become ready:

```bash
kubectl get pods -n ingress-nginx
kubectl get ingressclass
```

Point the DNS records from the configuration section at the ingress address. For a cluster using CoreDNS host overrides, add the records to the `coredns` ConfigMap in `kube-system`, then restart the CoreDNS pods. Use your own hostnames and IP address; the example values in the original README are site-specific.

## Install PostgreSQL

Create the database namespace and secrets. The workloads are deployed later with the environment overlay:

```bash
cp -n postgres/kubernetes/openagri_postgres.admin.secrets.example.yml postgres/kubernetes/openagri_postgres.admin.secrets.yml
cp -n postgres/kubernetes/openagri_postgres.db.secrets.example.yml postgres/kubernetes/openagri_postgres.db.secrets.yml
chmod 600 postgres/kubernetes/openagri_postgres.*.secrets.yml
# Edit both local files and replace all placeholder values before applying.
kubectl apply -f postgres/kubernetes/openagri_postgres.db.namespace.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.admin.secrets.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.db.secrets.yml
```

## Install MinIO

Prepare the ignored local credential file, replacing every placeholder. Existing deployments retain their local file; `cp -n` will not overwrite it.

```bash
cp -n minio/kubernetes/minio-credentials.env.example minio/kubernetes/minio-credentials.env
chmod 600 minio/kubernetes/minio-credentials.env
# Edit the local file with unique credentials and the correct webhook endpoint.
kubectl create namespace ilvo-openagri-minio --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic minio-credentials \
  --from-env-file=minio/kubernetes/minio-credentials.env \
  -n ilvo-openagri-minio --dry-run=client -o yaml | kubectl apply -f -
```

The setup job reads the MinIO root credentials, service-user passwords, and webhook endpoint from this Kubernetes Secret. The `init.sh` script does not print expanded commands or passwords.

The environment overlay creates the MinIO StatefulSet, persistent volume and claim, services, ingress rules, and setup job. The hostPath-backed volume retains data when the pod is recreated, but it is still tied to one node and is not a substitute for backups or replicated storage.

When migrating an existing installation from the former bare pod, back up MinIO data and stop that pod before applying the overlay. This avoids two MinIO processes using the same data directory:

```bash
kubectl delete pod minio -n ilvo-openagri-minio
```

Keep the existing data directory; the new persistent volume points to the configured host path. Do not remove the retained persistent volume or claim during this migration.

## Install InfluxDB

Create the namespace and install InfluxDB with the repository's values:

```bash
kubectl create namespace ilvo-openagri-tick --dry-run=client -o yaml | kubectl apply -f -
helm repo add influxdata https://helm.influxdata.com/
helm repo update
helm upgrade --install influxdb influxdata/influxdb2 \
  -f influxdb/kubernetes/influxdb-values.yaml \
  -n ilvo-openagri-tick
```

The InfluxDB ingress is created by the environment overlay.

Retrieve the generated admin password:

```bash
kubectl get secret influxdb-influxdb2-auth \
  -o "jsonpath={.data['admin-password']}" \
  -n ilvo-openagri-tick | base64 --decode
```

Use the password to sign in at the configured InfluxDB hostname. You can initialize the organization, bucket, and tokens from the InfluxDB CLI inside the pod:

```bash
kubectl exec -it --namespace ilvo-openagri-tick influxdb-influxdb2-0 -- /bin/sh
influx config create -n bootstrap --active \
  --username-password 'admin:<ADMIN_PASSWORD>' \
  --org <ORG_NAME> --host-url http://localhost:8086
influx org create -n <ORG_NAME> -d "OpenAgri organization"
influx bucket create -n <BUCKET_NAME> -o <ORG_NAME>
influx bucket ls -o <ORG_NAME>
influx auth create -o <ORG_NAME> -u <USER_NAME> \
  --description "Telegraf host" \
  --read-bucket <BUCKET_ID> --write-bucket <BUCKET_ID>
```

Replace the angle-bracket placeholders with your values; note the bucket ID for token creation. Create a separate token for the Kubernetes Telegraf installation if appropriate. Enter tokens in `telegraf/kubernetes/telegraf-values.yaml` and `telegraf/systemd/telegraf-host.conf`. Grant only the bucket permissions each client needs, and do not use credentials copied from an example or another deployment.

## Install Streamlit

For a new checkout, create the local environment file and replace its placeholders. Keep it local; it will be loaded into a namespaced Kubernetes Secret at runtime, not copied into the image or mounted from the node.

```bash
cp -n streamlit/workspaces/.env.example streamlit/workspaces/.env
chmod 600 streamlit/workspaces/.env
kubectl create namespace ilvo-openagri-streamlit --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic streamlit-runtime \
  --from-env-file=streamlit/workspaces/.env \
  -n ilvo-openagri-streamlit --dry-run=client -o yaml | kubectl apply -f -
```

The environment overlay sets the Streamlit image. Either make that image available to the cluster or build and push your own, then set the `streamlit-image` literal in the overlay to its name and tag:

```bash
cd streamlit
docker build -f Dockerfile -t <REGISTRY>/openagri-streamlit:<TAG> .
docker push <REGISTRY>/openagri-streamlit:<TAG>
cd ..
```

The host-level Dash systemd unit is a separate deployment from the Kubernetes Streamlit container. It expects the application under `/opt/openagri/streamlit`, an `openagri` service account, and a runtime `workspaces/.env` file; install it there or adjust the unit for your host. Both entry points use the `workspaces/dash_pages/` page tree for Dash or the `workspaces/pages/` tree for Streamlit.

## Apply Kubernetes Manifests

After preparing the PostgreSQL, MinIO, and Streamlit secrets and ensuring the Streamlit image is available, apply the selected environment overlay:

```bash
kubectl apply -k deploy/overlays/ilvo
```

For a copied environment overlay, replace `ilvo` with its directory name. The overlay applies the PostgreSQL, MinIO, Streamlit, Grafana, and ingress resources. Check the workloads:

```bash
kubectl get pods,pvc -n ilvo-openagri-postgres
kubectl get pods,jobs -n ilvo-openagri-minio
kubectl rollout status deployment/ilvo-openagri-streamlit -n ilvo-openagri-streamlit
```

After deployment, open the configured pgAdmin hostname, register the server using `postgres-service.ilvo-openagri-postgres.svc.cluster.local` as its address, and enter the database credentials from your configured secret. Connect to the intended database and run [postgres/create_tables.sql](postgres/create_tables.sql) to create the application tables.

## Configure Grafana

The environment overlay includes Grafana's namespace, persistent volume claim, deployment, service, and ingress. Check it with `kubectl get pods,pvc -n ilvo-grafana`.

The claim requires a working default storage class, or a storage class/PersistentVolume configured for your cluster. Set a unique Grafana administrator password and configure the InfluxDB data source using a suitably restricted token.

## Install Telegraf

Telegraf has a Kubernetes deployment and a separate host-level systemd service. Install it after InfluxDB is available and its API token has been configured.

For a new checkout, make local copies of the example configurations and enter the correct endpoint, organization, bucket, and token. The copy commands preserve existing local files.

```bash
cp -n telegraf/kubernetes/telegraf-values.example.yaml telegraf/kubernetes/telegraf-values.yaml
cp -n telegraf/systemd/telegraf-host.example.conf telegraf/systemd/telegraf-host.conf
chmod 600 telegraf/kubernetes/telegraf-values.yaml telegraf/systemd/telegraf-host.conf
```

For the Kubernetes DaemonSet:

```bash
helm upgrade --install influx-telegraf influxdata/telegraf-ds \
  -n ilvo-openagri-tick \
  -f telegraf/kubernetes/telegraf-values.yaml
kubectl apply -f telegraf/kubernetes/telegraf-service.yaml
```

For a Debian/Ubuntu Linux host, add InfluxData's signed package repository and install Telegraf:

```bash
wget -q https://repos.influxdata.com/influxdata-archive_compat.key -P /tmp
gpg --show-keys --with-fingerprint --with-colons /tmp/influxdata-archive_compat.key 2>&1 \
  | grep -q '^fpr:\+9D539D90D3328DC7D6C8D3B9D8FF8E1F7DF8B07E:$' \
  && cat /tmp/influxdata-archive_compat.key \
  | gpg --dearmor \
  | sudo tee /etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg > /dev/null
echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg] https://repos.influxdata.com/debian stable main' \
  | sudo tee /etc/apt/sources.list.d/influxdata.list
sudo apt-get update
sudo apt-get install telegraf
```

Verify the signing key fingerprint against InfluxData's current installation documentation before using this command. Then update `telegraf/systemd/telegraf-host.conf` with the correct endpoint and token. Install the configured file at Telegraf's standard config path; the unit uses the package's `telegraf` account and does not depend on the checkout path:

```bash
sudo install -o telegraf -g telegraf -m 600 telegraf/systemd/telegraf-host.conf /etc/telegraf/telegraf.conf
sudo cp telegraf/systemd/telegraf.service /etc/systemd/system/telegraf.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegraf
sudo systemctl status telegraf
```

## Verify the Deployment

Check workloads and ingress resources across namespaces:

```bash
kubectl get pods -A
kubectl get ingress -A
kubectl get events -A --sort-by=.lastTimestamp
```

For a workload that is not ready, inspect its pod and logs:

```bash
kubectl describe pod <POD_NAME> -n <NAMESPACE>
kubectl logs <POD_NAME> -n <NAMESPACE>
```

Confirm that DNS resolves each configured hostname to the ingress address and that each service is reachable. The manifests do not configure TLS certificates; add TLS and enforce HTTPS before exposing services beyond a trusted network.

## AI Webserver

The AI webserver is maintained separately. Follow the installation instructions in the [OpenAgri AI webserver repository](https://gitlab.ilvo.be/openagri/openagri_ai_webserver).