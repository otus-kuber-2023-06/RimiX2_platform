#/bin/bash
kubectl delete deployment mysql-instance
kubectl delete pvc mysql-instance-pvc
kubectl delete pv mysql-instance-pv
kubectl delete svc mysql-instance
kubectl delete -f ../deploy/cr.yml
kubectl apply -f ../deploy/cr.yml
