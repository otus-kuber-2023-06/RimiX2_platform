#7 kubernetes-operators (kopf)

https://cdn.otus.ru/media/public/66/db/Kubernetes_operators_HW-139042-66dbcd.pdf

`kubernetes-operators/deploy/`
`kubernetes-operators/build/`

kubectl apply -f deploy/crd.yml
kubectl apply -f deploy/cr.yml

kopf run mysql-operator.py --verbose

export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
kubectl exec -it $MYSQLPOD -- mysql -uroot -potuspassword -e "insert into test (name) values ('new 333')" otus-database
kubectl exec -it $MYSQLPOD -- mysql -uroot -potuspassword -e "select * from test" otus-database


1) operator docker image
2) operator k8s pack - deployment, rbac, crd