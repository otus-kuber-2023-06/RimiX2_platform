#/bin/bash
kubectl delete deployment mysql-instance
kubectl delete pvc mysql-instance-pvc
kubectl delete pv mysql-instance-pv
kubectl delete svc mysql-instance
kubectl delete job/backup-mysql-instance-job
kubectl delete pvc/backup-mysql-instance-pvc
kubectl delete pv/backup-mysql-instance-pv
kubectl delete deployment/mysql-operator
kubectl delete -f ../deploy/cr.yml
#kubectl apply -f ../deploy/cr.yml
