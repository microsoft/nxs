#!/bin/bash

mkdir -p /root/.kube
cp -f /mnt/secrets-store/AksKubeConfig /root/.kube/config
kubectl get pods

export PYTHONPATH=/app
python3 apps/vehicle_counting/api/app.py