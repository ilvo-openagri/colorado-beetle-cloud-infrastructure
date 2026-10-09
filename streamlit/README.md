# Create docker image:
docker build -f Dockerfile -t <REGISTRY>/openagri-streamlit:<TAG> .
docker push <REGISTRY>/openagri-streamlit:<TAG>

# Install the openagri Streamlit server in kubernetes:
kubectl apply -k deploy/overlays/<environment>
kubectl rollout status deployment/ilvo-openagri-streamlit -n ilvo-openagri-streamlit
kubectl exec --stdin --tty -n ilvo-openagri-streamlit deployment/ilvo-openagri-streamlit -- /bin/bash

The container starts `streamlit_app.py` and uses the Streamlit `pages/` directory. The separate host-level Dash service starts `dash_app.py` and uses `dash_pages/`; it is not included in this image. Provide Streamlit settings through the `streamlit-runtime` Kubernetes Secret, not an image-baked `.env` file.


# Issues

## TLS issue
If certificate verification reports that the requested host is not listed in the certificate's Subject Alternative Names (SANs), issue a certificate containing the DNS names or IP addresses used by clients.

microk8s config | tee ~/.kube/config
sudo microk8s refresh-certs -e ca.crt
