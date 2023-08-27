# 6 (kubernetes-templating) - minikube (k8s 1.21.14)

## Nginx Ingress 



Установка Nginx Ingress из чарта:
```
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace=nginx-ingress --create-namespace
```
Проверка работы установленного контроллера:
```
kubectl create deployment static-site --image=dockersamples/static-site --port=80
kubectl expose deployment/static-site --port 80 --target-port 80 
kubectl create ingress static-site --rule=test.dev.ganiev.su/static-site=static-site:80 --class=nginx --annotation=nginx.ingress.kubernetes.io/rewrite-target=/
curl -IL http://test.dev.ganiev.su/static-site
```

## Cert Manager

Предварительная установка CRD, необходимых для работы оператора cert-manager в k8s:
```
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.crds.yaml
```
Установка из чарта:
```helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager --wait --namespace=cert-manager --create-namespace
```

Установка необходимых для работы с Let's Encrypt ресурсов cert-manager - `Issuer` и `ClusterIssuer`:
```
kubectl apply -f .\kubernetes-templating\cert-manager\le-acme-http-issuer.yaml
kubectl apply -f .\kubernetes-templating\cert-manager\le-acme-http-staging-issuer.yaml
```
Теперь при заведении нового Ingress для автоматического получения и продления сертификата TLS от Let's Encrypt необходимо добавить аннотацию и секрет в метадату и спецификацию, как пример, для хоста test.dev.ganiev.su:
```
metadata:
    annotations:
        cert-manager.io/issuer: "letsencrypt-staging"
```
```
spec:
    tls:
        - hosts:
            - test.dev.ganiev.su
            secretName: letsencrypt-staging
```            

## Chartmuseum

Добавление репозитория для поиска и установки чарта:
```
helm repo add chartmuseum https://chartmuseum.github.io/charts
helm repo update
helm search repo chartmuseum --versions
```
Для настройки чарта (в частности ingress) необходимо поправить values-файл из чарта и сохранить его:
```
helm show values chartmuseum/chartmuseum > chartmuseum/values.yaml
```

Установка чарта chartmuseum последней версии:
```
helm upgrade --install chartmuseum chartmuseum/chartmuseum -f kubernetes-templating/chartmuseum/values.yaml \
--namespace=chartmuseum --create-namespace --set persistence.enabled=true,env.open.DISABLE_API=false
helm ls -n chartmuseum
kubectl get events -n chartmuseum --sort-by=.lastTimestamp
```

### * Работа с репозиторием chartmuseum производится через его API:

https://github.com/helm/chartmuseum - документация

`GET /api/charts` - получить список всех чартов  
`GET /api/charts/mychart` - получить список всех версий mychart  
`GET /api/charts/mychart/0.1.2` - получить описание mychart версии 0.1.2  
`GET /api/charts/mychart/0.1.2/templates` - получить темплейты mychart версии 0.1.2  
`GET /api/charts/mychart/0.1.2/values` - получить файл с настраиваемыми переменными для mychart версии 0.1.2  
`HEAD /api/charts/mychart` - проверка наличия mychart (любой версии)  
`HEAD /api/charts/mychart/0.1.2` - проверка наличия mychart версии 0.1.2  
`POST /api/charts` - загрузить новую версию чарта  
`POST /api/prov` - загрузить подпись чарта  
`DELETE /api/charts/mychart/0.1.2` - удалить версию 0.1.2 mychart (вместе с подписью)  

Пример загрузки новой версии чарта с помощью curl:
```
curl -X POST --data-binary "@mychart-0.1.3.tgz" https://chartmuseum.dev.ganiev.su/api/charts
```
Установка чарта из репозитория chartmuseum стандратная - с предварительным добавлением репозитория в helm. Пример:
```
helm repo add mychartmuseum https://chartmuseum.dev.ganiev.su
helm install mychartmuseum/mychart --generate-name
```
## Harbor

Добавление репозитория для установки чарта:
```
helm repo add harbor https://helm.goharbor.io
helm repo update
```
Для настройки чарта (в частности ingress) необходимо поправить values-файл из чарта и сохранить его:
```
helm show values harbor/harbor > harbor/values.yaml
```
Установка harbor из чарта:
```
helm upgrade --install harbor harbor/harbor -f kubernetes-templating/harbor/values.yaml --namespace=harbor --create-namespace 
```

## * (Helmfile)

`kubernetes-templating/helmfile/helmfile.yaml` - комплект helm-чартов
`kubernetes-templating/helmfile/helmfile-nested.yaml` - вложенный helmfile

Рендер комплекта чартов и применение helmfile:
```
helmfile template  
helmfile apply  
```

## * Свой helm-чарт

`kubernetes-templating/hipster-shop/templates/all-hipster-shop.yaml` - все файлы манифестов всех сервисов приложения hipster-shop  
`kubernetes-templating/hipster-shop/values.yaml` - файл c параметрами шаблонизации

Установка из helm-чарта:
```
helm dependency update kubernetes-templating/hipster-shop  
helm upgrade --install hipster-shop kubernetes-templating/hipster-shop --namespace hipster-shop --create-namespace
```

### * Дополнительное (chart dependencies)

Вывод сервиса `redis` в отдельный чарт-зависимость.

`kubernetes-templating/hipster-shop/Chart.yaml` - указаны зависимости, в том числе для Redis
`kubernetes-templating/hipster-shop/values.yaml` - настроенные переменные для Redis

## helm-secrets

Cервис frontend вынесен из чарта hipster-shop в отдельный чарт `frontend`.

`kubernetes-templating/frontend/charts` - все манифесты сервиса frontend.

Шифрование секретов с помощью плагина helm-secrets, pgp-ключа и утилиты `sops`.
```
helm plugin install https://github.com/futuresimple/helm-secrets
gpg --full-generate-key  
gpg -k  
sops -e -i --pgp 9DE1B26A51D0265C475529092FE6BC985112D9E1 kubernetes-templating/frontend/secrets.yaml 
```
Установка чарта `frontend` с расшифровкой секрета на лету:
```
helm secrets upgrade --install frontend kubernetes-templating/frontend --namespace hipster-shop -f kubernetes-templating/frontend/values.yaml -f kubernetes-templating/frontend/secrets.yaml
```

Расшифровка и сохранение файла секрета чарта `frontend`:
```
sops -d -i --pgp 9DE1B26A51D0265C475529092FE6BC985112D9E1 ../../frontend/secrets.yaml
```
`repo.sh` - Shell-скрипт добавления репозитория myrepo  

Отправка чарта в репозиторий chartmuseum:
```
helm package kubernetes-templating/frontend  
curl -X POST --data-binary "@frontend-0.1.0.tgz" https://chartmuseum.dev.ganiev.su/api/charts 
```
Обнлвение зависимостей чарта `hipster-shop`:
helm dependency update kubernetes-templating/hipster-shop  

## kubecfg (jsonnet)

Сервисы paymentservice и shippingservice выведены из чарта hipster-shop для дальнейшей их шаблонизации и установки с помощью jsonnet (kubecfg).

`kubernetes-templating/kubecfg//*.yaml` - манифесты as-is выведенных сервисов 

Установка (обновление релиза) hipster-shop без сервисов paymentservice и shippingservice:
```
helm upgrade --install hipster-shop ..\hipster-shop --namespace hipster-shop --create-namespace  
```
Установка kubecfg из go:
```
go install github.com/kubecfg/kubecfg@latest
```
Существующие библиотеки libsonnet для шаблонизации манифестов k8s:
 - https://github.com/kube-libsonnet/kube-libsonnet (former bitnami project)
 - https://github.com/jsonnet-libs/k8s-libsonnet

Можно подключить библиотеки несколькими способами, все они предполагают копирование необходимых файлов и указание пути до них в импорте шаблона jsonnet.

Вариант 1: Установка json-bundler (jb) из go и последующая установка библиотеки libsonnet
```
go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@latest
jb init  
jb install github.com/kube-libsonnet/kube-libsonnet
```

Вариант 2: Получение архива из github и его распаковка:
```
wget https://github.com/kube-libsonnet/kube-libsonnet/archive/refs/heads/master.zip -O temp.zip
unzip temp.zip
rm temp.zip
```
Вариант 3: Использование GIT-подмодуля:
```
git submodule add https://github.com/kube-libsonnet/kube-libsonnet 
```
Использован вариант 1. В импорте указан путь `vendor/github.com/kube-libsonnet/kube-libsonnet/kube.libsonnet`.

`kubernetes-templating/hipster-shop/kubecfg/services2.jsonnet` - шаблон jsonnet для обоих сервисов.

Валидация и установка шаблонизированных сервисов:
```
kubecfg validate services2.jsonnet
kubecfg update services2.jsonnet --namespace hipster-shop
```
## * kapitan (jsonnet)

Сервис cartservice выведен из чарта hipster-shop для шаблонизации и установки с помощью kapitan.

`kubernetes-templating/jsonnet/cs/*.yaml` - манифесты cartservice as-is

Установка (обновление релиза) hipster-shop без сервиса cartservice:
```
helm upgrade --install hipster-shop ..\hipster-shop --namespace hipster-shop --create-namespace  
```

Инициализация структуры папок:
```
kapitan init
```
Структура:
- __components__ - компоненты шаблонизируемого приложения (шаблоны, скрипты и пр.)
- __inventory__ 
    - __classess__ - параметризация компонентов
    - __targets__ - определение состава компонентов для целевой установка

Компиляция шаблонов (создания манифестов и других файлов в папке compiled):
```
kapitan compile
```
Установка манифестов с помошью сгенерированного скрипта:
```
compiled/cartservice/scripts/apply.sh
```

## kustomize (Патчи манифестов)

Сервис productcatalogservice выведен из чарта hipster-shop для кастомизации и установки с помощью kustomize.

Установка (обновление релиза) hipster-shop без сервиса productcatalogservice:
```
helm upgrade --install hipster-shop ..\hipster-shop --namespace hipster-shop --create-namespace  
```
В папке base созданы исхождные манифесты (deployment и сервис) для кастомизации
`kubernetes-templating/kustomize/base/kustomize.yml` - файл кастомизации для base

Создан оверлей с новым namespace, префиксом имени ресурсов и патчами для изменения типа сервиса и использования переменных окружения из configMap.

`kubernetes-templating/kustomize/overlays/test/kustomize.yml` - файл кастомизации для test на базе base  
`kubernetes-templating/kustomize/overlays/test/envs.config` - файл, используемый в генераторе ConfigMap  
`kubernetes-templating/kustomize/overlays/test/nodeport.yml` - патч сервиса  
`kubernetes-templating/kustomize/overlays/test/patch_deployment_with_envs.json` - патч деплоймента  

Рендер пропатченных манифестов для окружения test:
```
kubectl kustomize overlays/test
```

Установка кастомизированных манифестов:
```
kubectl apply -k base
kubectl create namespace hipster-shop-test
kubectl apply -k overlays/test
```