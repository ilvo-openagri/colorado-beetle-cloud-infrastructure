# OpenAgri SIP3 Cloud Infrastructure

This repository contains the application and infrastructure configuration used to deploy the OpenAgri SIP3 cloud services. It brings together the dashboard, data services, object storage, ingress, and monitoring components on a Kubernetes cluster.

## Project Overview

The deployment is organized around these services:

- **Streamlit** provides the OpenAgri web dashboard and application pages.
- **PostgreSQL** stores application records and relational data.
- **MinIO** provides S3-compatible storage for images and other application objects.
- **InfluxDB and Telegraf** collect and store host and Kubernetes runtime metrics.
- **Grafana** provides an optional metrics dashboard.
- **NGINX Ingress** routes configured hostnames to services inside the cluster.

The AI webserver is maintained separately; see the [AI webserver project](https://gitlab.ilvo.be/openagri/openagri_ai_webserver).

## Installation

For prerequisites, configuration guidance, and the deployment sequence, see the [installation guide](INSTALL.md). The guide covers ingress and DNS, PostgreSQL, MinIO, InfluxDB, Streamlit, optional Grafana, Telegraf, and deployment checks.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `streamlit/` | Streamlit application source, container build, and Kubernetes deployment |
| `postgres/` | PostgreSQL and pgAdmin manifests, credentials configuration, and schema SQL |
| `minio/` | MinIO deployment and bucket, user, policy, and webhook initialization |
| `influxdb/` | InfluxDB Helm values and ingress configuration |
| `telegraf/` | Kubernetes Telegraf configuration and host systemd service |
| `grafana/` | Optional Grafana Kubernetes resources |
| `ingress/` | NGINX ingress controller configuration |
| `create_image_list.sh` | Collects pod image references and exports matching MicroK8s containerd images |
| `import_images.sh` | Imports exported images into MicroK8s containerd |
| `verify_pod_health.sh` | Checks pod status and whether referenced images are available locally |

## Deployment Model

The manifests were developed for MicroK8s on a Linux host and include Kubernetes resources, Helm chart configuration, and host-level systemd configuration. Several resources assume a single node and local storage. Host paths, node selectors, ingress hostnames, and storage settings may need changes for another cluster.

The image export and import scripts support preparing a cluster with limited or no registry access. They use `microk8s kubectl` and `microk8s ctr`, so they are intended for a MicroK8s host.

## Configuration and Security

Review the manifests and configuration files before applying them. Some values are deployment-specific, including host paths and DNS names. Create credential files locally from the `.example` templates in [INSTALL.md](INSTALL.md); real credential files are ignored by Git and MinIO credentials are provisioned as a Kubernetes Secret. Rotate any credentials used by earlier deployments or published commits. The supplied ingress manifests do not configure TLS.
