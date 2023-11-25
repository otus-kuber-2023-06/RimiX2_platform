#7 kubernetes-operators (kopf)

Оператор = Контроллер (Pod с кодом работы) + CRD (CustomResourceDefinition)

Контроллер подписывается на необходимые события над ресурсами типов, описанных в CRD.
И в соответствии с необходимой логикой работы выполняет некоторые действия в кластере через API-сервер.  

Создадим оператор для установки сервера Mysql определенной версии в кластере вместе с определяемым размером диска для него и сетевого сервиса для обращения к нему. Оператор будет создавать резервную копию диска экземлпяра сервера, а также восстанавливать сервер с неё.

https://cdn.otus.ru/media/public/66/db/Kubernetes_operators_HW-139042-66dbcd.pdf

`kubernetes-operators/deploy/` - манифесты для работы контроллера и тестирования его работы  
`kubernetes-operators/build/` - файлы для cоздания образа оператора - Dockerfile, программный код, шаблоны манифестов в templates

Внесем в API-сервер новый тип ресурса "MySQL", который будет обрабатывать контроллер c помощью его описания (CRD):
```
# kubectl apply -f deploy/0-crd.yml
customresourcedefinition.apiextensions.k8s.io/mysqls.otus.homework created
```

## Код контроллера

Необходимые условия для работы контроллера:
- Динамическое выделение PV
- Поддержка увеличения размера у default StorageClass (allowVolumeExpansion: true)

### Подготовка
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Контроллер будет обрабатывать два типа событий:

1. При создании объекта типа ( kind: mySQL ), он будет:
    - Cоздавать PersistentVolume, PersistentVolumeClaim, Deployment, Service для mysql
    - Создавать PersistentVolume, PersistentVolumeClaim для бэкапов базы данных, если их еще нет
    - Либо пытаться восстановиться из бэкапа
2. При удалении объекта типа ( kind: mySQL ), он будет:
    - Удалять все успешно завершенные backup-job и restore-job
    - Удалять PersistentVolume, PersistentVolumeClaim, Deployment, Service для mysql

`kubernetes-operators/build/mysql-operator.py` - код контроллера с использованием фреймфорка kopf

kubectl apply -f deploy/6-cr.yml

Запуск контроллера локально (с подключением к кластеру):
```
kopf run mysql-operator.py --verbose
```

Создание экземпляра ресурса типа "MySQL"
```
kubectl apply -f deploy/6-cr.yml
```

## Проверка восстановления БД из резервной копии
export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
kubectl exec -it $MYSQLPOD -- mysql -uroot -potuspassword -e "insert into test (name) values ('new 333')" otus-database
kubectl exec -it $MYSQLPOD -- mysql -uroot -potuspassword -e "select * from test" otus-database


## Установка контроллера в кластер

### Сборка образа

### Установка необходимых манифестов для работы контроллера

Добавим кластерную роль для работы оператора с правами на все действия с ресурсами необходимыми для работы оператора:
```
# kubectl apply -f deploy/2-cluster-role.yml
```
Создадим сервисную учетную запись, под которой будет работать контроллер:
```
# kubectl apply -f deploy/3-service-account.yml
```
Свяжем эту запись с созданной ранее ролью:
```
# kubectl apply -f deploy/4-cluster-role-binding.yml
```

## (*)  status subresource

• Исправить контроллер, чтобы он писал в status subresource
• Описать изменения в README.md (показать код, объяснить, что он делает)
• В README показать, что в status происходит запись
• Например, при успешном создании mysql-instance, kubectl describe
mysqls.otus.homework mysql-instance может показывать:
    Status:
    Kopf:
    mysql_on_create:
    Message: mysql-instance created without restore-job

## (*)  password changing

• Добавить в контроллер логику обработки изменений CR:  
    ◦ Например, реализовать смену пароля от MySQL, при изменении  
этого параметра в описании mysql-instance
• В README:
    ◦ Показать, что код работает
    ◦ Объяснить, что он делает
