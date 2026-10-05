# OpenAgri Cloud Infrastructure Installation

This guide describes installing the services in this repository on a Linux host running Kubernetes. It expands the deployment notes in [README.md](README.md) into an end-to-end sequence.

The manifests were written for a single-node MicroK8s installation and include host-specific settings. Review the configuration section before applying them to another machine. These manifests configure HTTP ingress; TLS, backups, and production hardening are deployment-specific and are not configured here.

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

1. Replace the example ingress hostnames in the manifests with names available in your DNS. The current hostnames include `streamlit.ilvonuc.com`, `pgadmin.ilvonuc.com`, `minio.ilvonuc.com`, `api.minio.ilvonuc.com`, `influx.ilvonuc.com`, and `grafana.ilvoserver.com`.
2. Update machine-specific `hostPath` values and the MinIO `nodeSelector` in the manifests. Create the required directories on the Kubernetes node and ensure the pods can write to their mounted storage. In particular, review the paths in the PostgreSQL, MinIO, and Streamlit manifests.
3. Create local credential files from the `.example` files described below and replace every placeholder. These real files are ignored by Git; do not force-add them.
4. Rotate any credentials that have been used in an earlier deployment or published commit. Removing a file from the latest commit does not invalidate its credentials.
5. Configure InfluxDB and Telegraf with the correct organization, bucket, endpoint, and API tokens. Keep tokens in the ignored local Telegraf configuration files.
6. Streamlit credentials are loaded from the mounted local `.env` file at runtime. The Dockerfile does not copy `.env` into the image.

Ingress hostnames and storage paths are defined in the manifests rather than generated from one central configuration file, so update each relevant manifest consistently.

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

Create the database namespace and secrets, then deploy PostgreSQL and pgAdmin:

```bash
cp -n postgres/kubernetes/openagri_postgres.admin.secrets.example.yml postgres/kubernetes/openagri_postgres.admin.secrets.yml
cp -n postgres/kubernetes/openagri_postgres.db.secrets.example.yml postgres/kubernetes/openagri_postgres.db.secrets.yml
chmod 600 postgres/kubernetes/openagri_postgres.*.secrets.yml
# Edit both local files and replace all placeholder values before applying.
kubectl apply -f postgres/kubernetes/openagri_postgres.db.namespace.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.admin.secrets.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.db.secrets.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.db.deployment.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.admin.deployment.yml
```

Check pod status:

```bash
kubectl get pods,pvc -n ilvo-openagri-postgres
```

Open the configured pgAdmin hostname, register the server using `postgres-service.ilvo-openagri-postgres.svc.cluster.local` as its address, and enter the database credentials from your configured secret. Connect to the intended database and run [postgres/create_tables.sql](postgres/create_tables.sql) to create the application tables.

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

After updating the node selector and host paths, apply the MinIO resources:

```bash
kubectl apply -f minio/kubernetes/openagri_minio.app.deployment.yml
kubectl get pods,jobs -n ilvo-openagri-minio
```

The manifest creates the MinIO pod, services, ingress rules, and a setup job. The job creates the application buckets, users, policy, and webhook event. Verify that the MinIO pod is ready and the `minio-setup` job completes before configuring applications that use object storage.

## Install InfluxDB

Create the namespace and install InfluxDB with the repository's values:

```bash
kubectl create namespace ilvo-openagri-tick
helm repo add influxdata https://helm.influxdata.com/
helm repo update
helm upgrade --install influxdb influxdata/influxdb2 \
  -f influxdb/kubernetes/influxdb-values.yaml \
  -n ilvo-openagri-tick
kubectl apply -f influxdb/kubernetes/influxdb-ingress.yaml
```

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

For a new checkout, create the local environment files and replace their placeholders. The Kubernetes manifest mounts `streamlit/kubernetes/streamlit-env` at `/env`; that directory must be present on the selected node.

```bash
cp -n streamlit/workspaces/.env.example streamlit/workspaces/.env
cp -n streamlit/workspaces/.env.example streamlit/kubernetes/streamlit-env/.env
chmod 600 streamlit/workspaces/.env streamlit/kubernetes/streamlit-env/.env
```

The deployment references the image `jbauwens/openagri-streamlit:1.0.6`. Either make the configured image available to the cluster or build and push your own image, then update the deployment manifest to use its image name and tag:

```bash
cd streamlit
docker build -f Dockerfile -t <REGISTRY>/openagri-streamlit:<TAG> .
docker push <REGISTRY>/openagri-streamlit:<TAG>
cd ..
```

Apply the deployment and wait for it to roll out:

```bash
kubectl apply -f streamlit/kubernetes/openagri_streamlit.app.deployment.yml
kubectl rollout status deployment/ilvo-openagri-streamlit \
  -n ilvo-openagri-streamlit
```

The manifest mounts a host directory for Streamlit configuration. Update that host path to a directory that exists on the Kubernetes node before applying it.

## Install Grafana (Optional)

The Grafana manifest includes its namespace, persistent volume claim, deployment, service, and ingress:

```bash
kubectl apply -f grafana/grafana-config.yaml
kubectl get pods,pvc -n ilvo-grafana
```

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

Verify the signing key fingerprint against InfluxData's current installation documentation before using this command. Then update `telegraf/systemd/telegraf-host.conf` with the correct endpoint and token. Edit `telegraf/systemd/telegraf.service` so `ExecStart` points to that config in this checkout and `User` is a valid local account, then install and enable the service:

```bash
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