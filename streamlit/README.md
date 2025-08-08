# Create docker image:
sudo docker build -f Dockerfile -t openagri-streamlit:latest .
sudo docker tag openagri-streamlit:latest jbauwens/openagri-streamlit:0.23
sudo docker push jbauwens/openagri-streamlit:0.23

# Install the openagri Streamlit server in kubernetes:
kubectl apply -f kubernetes/openagri_streamlit.app.deployment.yml
kubectl rollout restart deployment ilvo-openagri-streamlit -n ilvo-openagri-streamlit
kubectl exec --stdin --tty -n ilvo-openagri-streamlit deployment/ilvo-openagri-streamlit -- /bin/bash


# Issues

## Tls issue:
tls: failed to verify certificate: x509: certificate is valid for 172.17.0.1, 192.168.251.174, 10.8.0.17, not 192.168.251.185

microk8s config | tee ~/.kube/config
sudo microk8s refresh-certs -e ca.crt
