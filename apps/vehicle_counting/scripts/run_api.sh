#!/bin/bash

mkdir -p /root/.kube
cp -f /mnt/secrets-store/AksKubeConfig /root/.kube/config
kubectl get pods

export PYTHONPATH=/app
python3 apps/vehicle_counting/api/app.py &

while true
do
	kubectl delete job $(kubectl get job -n nxsapp -o=jsonpath='{.items[?(@.status.succeeded==1)].metadata.name}') -n nxsapp
	sleep 60
done