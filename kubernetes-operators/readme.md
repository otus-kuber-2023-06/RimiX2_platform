#7 kubernetes-operators (kopf)

Оператор = Контроллер (Pod с кодом работы) + CRD (CustomResourceDefinition)

Контроллер подписывается на необходимые события над ресурсами типов, описанных в CRD.
И в соответствии с необходимой логикой работы выполняет некоторые действия в кластере через API-сервер.  
Находясь в бесконечно цикле, он, по сути, приводит состояние контролируемых объектов к желаемому (описанному в спецификации). Если состояние изменить не получается, контроллер повторяет попытки бесконечно.

Создадим оператор для установки сервера Mysql определенной версии в кластере вместе с определяемым размером диска для него и сетевого сервиса для обращения к нему. 
При удалении экземлпяра сервера оператор будет создавать резервную копию БД, а также восстанавливать БД с неё при повторном создании экземлпяра.

Кластер должен быть однонодовый, т.к. PVC (PersistenceVolumeClaim) будет использоваться типа "hostPath".

https://cdn.otus.ru/media/public/66/db/Kubernetes_operators_HW-139042-66dbcd.pdf

`kubernetes-operators/deploy/` - манифесты для работы контроллера и тестирования его работы  
`kubernetes-operators/build/` - файлы для cоздания образа оператора - Dockerfile, программный код, шаблоны манифестов в templates

Внесем в API-сервер новый тип ресурса "MySQL", который будет обрабатывать контроллер c помощью его описания (CRD):
```
# kubectl apply -f deploy/crd.yml
customresourcedefinition.apiextensions.k8s.io/mysqls.otus.homework created
```

## Код контроллера

Подготовка окружения:
```
# cd build
# python -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt
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

Запускаем контроллер локально (с подключением к API-серверу текущего контекста (из kubeconfig):
```
# kopf run mysql-operator.py --verbose
```

Создадим экземпляр ресурса типа mysql:
```
# kubectl apply -f deploy/cr.yml
```

Создадим тестовую таблицу в нем:
```
# export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
# kubectl exec -it $MYSQLPOD -- mysql -u root -potuspassword -e "CREATE TABLE test (id smallint unsigned not null \ auto_increment, name varchar(20) not null, constraint pk_example primary key (id) );" otus-database
```

Заполним её данными:
```
# kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "INSERT INTO test ( id, name) VALUES ( null, 'some data' );" otus-database
# kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "INSERT INTO test ( id, name ) VALUES ( null, 'some data-2' );" otus-database
```

## Проверка восстановления БД из резервной копии
```
# export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
# kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "insert into test (name) values ('new 333')" otus-database
# kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "select * from test" otus-database

# kubectl delete -f deploy/cr.yml

# kubectl create -f deploy/cr.yml

# export MYSQLPOD=$(kubectl get pods -l app=mysql-instance -o jsonpath="{.items[*].metadata.name}")
# kubectl exec -it $MYSQLPOD -- mysql -potuspassword -e "select * from test;" otus-database
```

## Установка контроллера в кластер

### Сборка образа и отправка в реестр

```
# cd build
# docker build -t ghcr.io/rimix2/mysqloperator:0.1.0 .
# docker login ghcr.io
# docker push ghcr.io/rimix2/mysqloperator:0.1.0
```

### Установка необходимых манифестов для работы контроллера

Добавим кластерную роль для работы оператора с правами на все действия с ресурсами необходимыми для работы оператора:
```
# kubectl apply -f deploy/role.yml
```
Создадим сервисную учетную запись "mysql-operator-sa", под которой будет работать контроллер:
```
# kubectl apply -f deploy/service-account.yml
```
Свяжем эту запись с созданной ранее ролью:
```
# kubectl apply -f deploy/role-binding.yml
```
Разворачиваем контроллер:
```
# kubectl apply -f deploy/deploy-operator.yml
```

## (*)  Status subresource

В код контроллера добавлен метод `update_status(body, msg)`, который обновляет поле в status subresource экземпляра mysql.  
Это происходит после попытки восстановления из бэкапа. Результат исполнения этой задачи отражается в поле "status.message".

```
# kubectl describe mysqls/mysql-instance
...
Status:
  Message:  Restoring DB have succeed
...
```

## (*)  Password changing

Будем реагировать на измененение пароля в ресурсе mysql.
В код контроллера добавляем метод `change_rootpswd(old, new, status, namespace, **kwargs)` с декоратором `@kopf.on.field` параметризованным на поле "password".
В методе происходит поиск пода и выполенение в нём SQL-запроса на смену пароля у пользователя root@localhost.