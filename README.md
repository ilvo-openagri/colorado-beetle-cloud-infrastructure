# Cloud infrastructure

This repository consist of all the dependencies that are required to set up the Openagri SIP3 cloud infrastructure.

## Mini PC

### DNS

Update coredns:

```bash
kubectl -n kube-system edit configmap coredns
#   NodeHosts: |                                          
#     ...
#     192.168.50.1 influx.ilvonuc.com   
```

### Postgres database

Set up the kubernetes environment:

```bash
kubectl apply -f postgres/kubernetes/openagri_postgres.db.namespace.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.admin.secrets.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.db.secrets.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.db.deployment.yml
kubectl apply -f postgres/kubernetes/openagri_postgres.admin.deployment.yml
```

Log in to the admin console (pgadmin.ilvonuc.com), and add the newly created server: postgres-service.ilvo-openagri-postgres.svc.cluster.local
Afterwards, create the tables using the postgres/create_tables.sql script.

### Streamlit webui

Set up the streamlit webui server:

```bash
kubectl apply -f streamlit/kubernetes/openagri_streamlit.app.deployment.yml
```

### Minio S3 server

Set up the Minio S3 server

```bash
kubectl apply -f minio/kubernetes/openagri_minio.app.deployment.yml
```

### Influxdb

Set up the influxdb server. First install it:

```bash
kubectl create namespace ilvo-openagri-tick
helm repo add influxdata https://helm.influxdata.com/
helm upgrade --install influxdb influxdata/influxdb2 -f influxdb/kubernetes/influxdb-values.yaml -n ilvo-openagri-tick
kubectl apply -f  influxdb/kubernetes/influxdb-ingress.yaml
```

To get the admin password:
```bash
echo $(kubectl get secret influxdb-influxdb2-auth -o "jsonpath={.data['admin-password']}" --namespace ilvo-openagri-tick | base64 --decode)
```

You can use this to login to influx.ilvonuc.com with username "admin".

Use the influx client to set-up the environment:
```bash
kubectl exec -i -t --namespace ilvo-openagri-tick influxdb-influxdb2-0 -- /bin/sh
influx config create -n admin_login --active --username-password admin:<PASSWORD_PREVIOUS_STEP> --org admin --host-url http://localhost:8086
influx org create -n ilvo -d "General ILVO organisation"
influx user create -n openagri -o ilvo -password [REDACTED]
influx bucket create -n openagri-bucket -o ilvo
influx bucket ls -o ilvo -n openagri-bucket # Note the ID
influx auth create -o ilvo -u openagri -description "Openagri RPI5" --read-bucket <BUCKET_ID> --write-bucket <BUCKET_ID> # Note the API token
influx auth create -o ilvo -u openagri -description "Openagri NUC" --read-bucket <BUCKET_ID> --write-bucket <BUCKET_ID> # Note the API token
```

The API tokens need to be filled in to the telegraf-values.yaml when setting up the telegraf environment.

### Telegraf

We rely on telegraf for monitoring the internal runtime parameters of the cloud/edge deployment.
For the cloud deployment, it consists of two seperate entities: inside kubernetes and on the linux host system.
Ensure that telegraf/kubernetes/telegraf-values.yaml and telegraf-host.conf consists of the correct influxdb API key (see cloud set-up).

To install telegraf in kubernetes:
```bash
helm upgrade --install influx-telegraf influxdata/telegraf-ds -n ilvo-openagri-tick -f telegraf/kubernetes/telegraf-values.yaml
```

To install it on the host system, first install telegraf:

```bash
wget -q https://repos.influxdata.com/influxdata-archive_compat.key -P /tmp
gpg --show-keys --with-fingerprint --with-colons /tmp/influxdata-archive_compat.key 2>&1 \
| grep -q '^fpr:\+9D539D90D3328DC7D6C8D3B9D8FF8E1F7DF8B07E:$' \
&& cat /tmp/influxdata-archive_compat.key \
| gpg --dearmor \
| sudo tee /etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg > /dev/null
echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg] https://repos.influxdata.com/debian stable main' \
| sudo tee /etc/apt/sources.list.d/influxdata.list
sudo apt-get update && sudo apt-get install telegraf
```

```bash
sudo ln -sf /home/jbauwens/openagri/cloud-infrastructure/telegraf/systemd/telegraf.service /etc/systemd/system
sudo systemctl daemon-reload
```

### AI webserver
Please refer to https://gitlab.ilvo.be/openagri/openagri_ai_webserver for the installation of the AI webserver.