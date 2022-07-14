#!/bin/bash

kubectl get jobs -n nxsapp | awk '{ print $1 }' | xargs kubectl delete job -n nxsapp
kubectl get pvc -n nxsapp | awk '{ print $1 }' | xargs kubectl delete pvc -n nxsapp