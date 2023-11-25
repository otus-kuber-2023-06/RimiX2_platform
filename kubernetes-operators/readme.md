#7 kubernetes-operators (kopf)

Оператор = Контроллер (Pod с кодом работы) + CRD (CustomResourceDefinition)

Контроллер подписывается на необходимые события над ресурсами типов, описанных в CRD.
И в соответствии с необходимой логикой работы выполняет некоторые действия в кластере через API-сервер.  
Находясь в бесконечно цикле, он, по сути, приводит состояние контролируемых объектов к желаемому (описанному в спецификации).

Создадим оператор для установки сервера Mysql определенной версии в кластере вместе с определяемым размером диска для него и сетевого сервиса для обращения к нему. 
При удалении экземлпяра ресурса оператор будет создавать резервную копию БД, а также восстанавливать сервер с неё при повторном создании экземлпяра ресурса.

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
    - Cоздавать PersistentVolume, PersistentVolumeClaim, Deployment, Service для экземлпяра ресурса типа mysql
    - Создавать PersistentVolume, PersistentVolumeClaim для задачи бэкапа базы данных, если их еще нет
    - Пытаться восстановиться из бэкапа
2. При удалении объекта типа ( kind: mySQL ), он будет:
    - Создавать бэкап БД
    - Удалять все успешно завершенные задачи по созданию бэкапа и восстановлению с него
    - Удалять PersistentVolume, PersistentVolumeClaim, Deployment, Service для экземлпяра ресурса типа mysql

`kubernetes-operators/build/mysql-operator.py` - код контроллера с использованием фреймфорка kopf

Запускаем контроллера локально (с подключением к API-серверу текущего контекста kubeconfig):
```
kopf run mysql-operator.py --verbose
```

Создадим экземпляр ресурса типа "MySQL"
```
kubectl apply -f deploy/6-cr.yml
```

Создадим тестовую таблицу в нем:
```
export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
kubectl exec -it $MYSQLPOD -- mysql -u root -potuspassword -e "CREATE TABLE test (id smallint unsigned not null auto_increment, name varchar(20) not null, constraint pk_example primary key (id) );" otus-database
```

Заполним её данными:
```
kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "INSERT INTO test ( id, name) VALUES ( null, 'some data' );" otus-database
kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "INSERT INTO test ( id, name ) VALUES ( null, 'some data-2' );" otus-database
```

## Проверка восстановления БД из резервной копии
export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "insert into test (name) values ('new 333')" otus-database
kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "select * from test" otus-database
kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "select * from test;" otusdatabase

kubectl delete mysqls.otus.homework mysql-instance

export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "select * from test;" otusdatabase

└── deploy
    ├── cr.yml
    ├── crd.yml
    ├── deploy-operator.yml
    ├── role-binding.yml
    ├── role.yml
    └── service-account.yml

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
