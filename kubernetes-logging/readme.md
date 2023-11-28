#9 Logging

## Infra

Чтобы выделить 3 из 4-х нод только для платформенной инфраструктуры, применим к ним Taint:
```
kubectl taint nodes node[1-3] node-role=infra:NoSchedule
```

В дальнейшем для разворачивания приложений на них, необьходимо указывать дополнительный Toleration к вышеуказанному Taint.

Укажем дополнительные метки ко всем нодам.
```
kubectl label nodes -l [1-3] role=infra
kubectl label nodes -l [4] role=workload
```

## Demo microservices


Установим демо-приложение из манифестов:
```
kubectl create ns demo
wget https://raw.githubusercontent.com/express42/otus-platform-snippets/master/Module-02/Logging/microservices-demo-without-resources.yaml
kubectl apply -f microservices-demo-without-resources.yaml -n demo
```

## Elastic Stack (fluent bit)


```
helm repo add elastic https://helm.elastic.co
helm repo add fluent https://fluent.github.io/helm-charts

kubectl create ns observe

helm show values elastic/elasticsearch > EFK/es-values.yml
helm upgrade --install elasticsearch elastic/elasticsearch --namespace observe --values elasticsearch.values.yaml
kubectl get secret elasticsearch-master-credentials -o=jsonpath='{.data.password}' -n observe | base64 --decode
helm show values elastic/kibana > EFK/kibana-values.yml
helm upgrade --install kibana elastic/kibana --namespace observe --values kibana.values.yaml
helm show values fluent/fluent-bit > EFK/f-bit-values.yml
helm upgrade --install fluent-bit fluent/fluent-bit --namespace observe --values fluent-bit.values.yaml
```

## Ingress Controller

```
helm show values ingress-nginx --repo https://kubernetes.github.io/ingress-nginx > ingress-nginx.values.yaml

helm upgrade --install ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace ingress-nginx --create-namespace --values ingress-nginx.values.yaml
```

## Prometheus Elasticsearch Exporter

```
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm show values prometheus-community/kube-prometheus-stack > prom-stack.values.yaml
helm upgrade --install prom-operator prometheus-community/kube-prometheus-stack --namespace observe --values prom-stack.values.yaml

helm show values prometheus-community/prometheus-elasticsearch-exporter > es-prom-exporter.values.yaml
helm upgrade --install es-prom-exporter prometheus-community/prometheus-elasticsearch-exporter --namespace observe --values es-prom-exporter.values.yaml
```

## (*) Duplicate field '@timestamp'

В моем случае не возникло такой проблемы. Как вариант, не указанный в методическом материале к ДЗ можно предложить убрать парсинг поля со временем, закомментировав и не в принципе не использовав директиву Time_Key в блоке [INPUT]

## Grafana Loki
```
helm install loki bitnami/grafana-loki -n observe -f loki.values.yaml
```
## K8s Event Logger
```
helm repo add deliveryhero https://charts.deliveryhero.io/
helm install event-logger deliveryhero/k8s-event-logger -n observe
```
## (*) Audit K8s logs

Включение или конфигурация журнала аудита в K8s производится через yaml-файл c манифестом политики, который указывается при запуске API-сервера в опции `--audit-policy-file`. В файле обязательно должны присутствовать правила аудита в блоке **rules**.

В правиле содержится:
1.  Степень аудита (None, Metadata, Request, RequestResponse)
2.  Инициатор-пользователь
3.  Инициатор-группа
4.  Группы и типы ресурсов
5.  Тип аудируемого действия (watch/list/get и пр.)

По умолчанию существет два бэкенда для сохранения журнала аудита. Один из них это запиcь в локальную файловую систему через и задаётся через опцию `--audit-log-path`, указывающую в какой файл писать журнал. Второй бэкенд - это вебхук. Записи аудита представляются в виде JSON-линий.

Для файлового бэкенда есть опции для ротации файлов:
- `-- audit-log-maxage` - срок
- `-- audit-log-maxbackup` - кол-во файлов
- `-- audit-log-maxsize` - размер

`audit-policy.yaml` - примерный манифест политики.

Если kube-apiserver запускается в виде пода, необходимо все файлы, которые будут указываться через опции подключать в виде томов. Если API-сервер запускается в виде сервиса ОС, файлы должны быть доступны в файловой системе.

## (*) Host logs

Организовать сбор логов с хостовой ОС можно используя уже развернутый daemonset с Fluent-bit из стека EFK. Т.к. при установке чарта к daemon-подам уже были примонтированы тома с локальной папкой /var/log, остается только добавить цепочку блоков с новым тегом "host.logs" в конфигурацию Fluent-bit:
- ***[INPUT]*** источник логов типа tail с путём /var/log/*.log (или конкретное имя лог-файла)
- ***[FILTER]*** c типом "record_modifier" для добавления полей с именем/IP хоста и путём лог-файла
- ***[OUTPUT]*** бэкенд в виде ранее развернутого elasticsearch 

Это можно сделать через апгрейд установки чарта Fluent-bit с добавлением в переменные config.[inputs,outputs,filters].
`fluent-bit.values.yaml` - файл для переопределения переменных чарта с изменениями для сбора хостовых логов. 

Сбор с помощью LOKI подразумевает аналогичные требования: присоединенный том типа hostPath c системной директорией /var/log к daemon-поду c Promtail и его конфигурация на источник в виде файлов из директории /var/log.