# Create docker image:
sudo docker build -f Dockerfile -t openagri-streamlit:latest .
sudo docker tag openagri-streamlit:latest jbauwens/openagri-streamlit:0.1
sudo docker push jbauwens/openagri-streamlit:0.1

# Install the openagri Streamlit server in kubernetes:
kubectl apply -f kubernetes/openagri_streamlit.app.deployment.yml
kubectl rollout restart deployment ilvo-openagri-streamlit -n ilvo-openagri-streamlit
kubectl exec --stdin --tty -n ilvo-tools openagri-streamlit-856968ffdd-n5p68 -- /bin/bash