# VEHICLE COUNTING APP

### Requirements
- ACR

### Build worker container and upload to your ACR
```
export ACR_LOGIN_SERVER_NAME=<YOUR ACR LOGIN SERVER NAME>
export ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER_NAME}.azurecr.io
docker build -f apps/vehicle_counting/Dockerfile.worker -t $ACR_LOGIN_SERVER/vcworker:v0.1 .

az login
az acr login -n $ACR_LOGIN_SERVER_NAME
docker push $ACR_LOGIN_SERVER/vcworker:v0.1
```

### Create vcapp namespace for vehicle counting app
```
kubectl create namespace vcapp
```

### Create secret to download containers
```
kubectl create secret docker-registry vcregcred -n vcapp \
            --docker-server ACR_LOGIN_SERVER \
            --docker-username=ACR_USER_NAME \
            --docker-password=ACR_USER_PASSWORD
```