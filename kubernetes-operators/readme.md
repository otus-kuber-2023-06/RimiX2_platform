#7 kubernetes-operators (kopf)

Оператор = Контроллер (Pod с кодом работы) + CRD (CustomResourceDefinition)

Контроллер подписывается на необходимые события над ресурсами типов, описанных в CRD.
И в соответствии с необходимой логикой работы выполняет некоторые действия в кластере через API-сервер.  

Создадим оператор для установки сервера Mysql определенной версии в кластере вместе с определяемым размером диска для него и сетевого сервиса для обращения к нему. Оператор будет создавать резервную копию диска экземлпяра сервера, а также восстанавливать сервер с неё.

https://cdn.otus.ru/media/public/66/db/Kubernetes_operators_HW-139042-66dbcd.pdf

`kubernetes-operators/deploy/` - манифесты для работы контроллера и тестирования его работы  
`kubernetes-operators/build/` - файлы для cоздания образа оператора - Dockerfile, программный код, шаблоны манифестов в templates

Внесем в API-сервер новый тип ресурса "MySQL" c помощью его описания (CRD):
```
# kubectl apply -f deploy/0-crd.yml
customresourcedefinition.apiextensions.k8s.io/mysqls.otus.homework created
```
Добавим кластерную роль для работы оператора с правами на все действия с ресурсами необходимыми для работы оператора:
```
# kubectl apply -f deploy/2-cluster-role.yml
```
```
# kubectl apply -f deploy/3-service-account.yml
```
```
# kubectl apply -f deploy/4-cluster-role-binding.yml
```

## Код контроллера

Необходимые условия для работы контроллера:
- Динамическое выделение PV
- Поддержка увеличения размера у default StorageClass (allowVolumeExpansion: true)

Контроллер будет обрабатывать два типа событий:
1. При создании объекта типа ( kind: mySQL ), он будет:
- Cоздавать PersistentVolume, PersistentVolumeClaim, Deployment, Service для mysql
- Создавать PersistentVolume, PersistentVolumeClaim для бэкапов базы данных, если их еще нет
- Пытаться восстановиться из бэкапа
2. При удалении объекта типа ( kind: mySQL ), он будет:
- Удалять все успешно завершенные backup-job и restore-job
- Удалять PersistentVolume, PersistentVolumeClaim, Deployment, Service для mysql

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

`kubernetes-operators/build/mysql-operator.py` - код контроллера с использованием фреймфорка kopf

kubectl apply -f deploy/cr.yml
kopf run mysql-operator.py --verbose

export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
kubectl exec -it $MYSQLPOD -- mysql -uroot -potuspassword -e "insert into test (name) values ('new 333')" otus-database
kubectl exec -it $MYSQLPOD -- mysql -uroot -potuspassword -e "select * from test" otus-database


1) operator docker image
2) operator k8s pack - deployment, rbac, crd