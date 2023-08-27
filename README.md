# OTUS k8s-platfrom homework

# 1 (kubernetes-intro)
## Pod

В результате удаления всех контейнеров через docker или подов через kubectl все они восстановились. Потому что за многими из них следит сервис "kubelet" на ноде (т.н. статические поды), а за динамическими - контроллер репликации.

`kubernetes-intro/web/Dockerfile` - файл для сборки образа с простым http-сервером и кастомным конфигом.

Сборка и загрузка в реестр образов для разных архитектур:
```
docker buildx build --push --platform linux/amd64,linux/arm64 --tag ghcr.io/rimix2/dockerfile-test:0.0.1 .
```

`kubernetes-intro/web-pod.yaml`
Манифест для разворачивания пода с init-контейнером, который генерирует контент для основного контейнера с образом http-сервера
###  * Дополнительное

`kubernetes-intro/frontend-pod-health.yaml`
Исправленный манифест с доавбленными необходимыми для работы пода переменными окружения

# 2 (kubernetes-controllers)
## Deployment / Probes

`kubernetes-controllers/*.yaml`  
Созданы манифесты для создания ресурсов deployment для paymentservice двух версий rimix/paysvc:0.0.1 и rimix/paysvc:0.0.2.  
Создан манифест для создания ресурса deployment для frontend версии rimix/otus:frontend2 c включенной ReadinessProbe
Появляется возможность откатывать через CI/CD:
```
kubectl rollout undo deployment/frontend
```
по результату получения:
```
kubectl rollout status deployment/frontend --timeout=60s
```
###  * Дополнительное 1 (MaxUnavailable и MaxSurge)

`kubernetes-controllers/paymentservice-deployment-bg.yaml` -
манифест для обновления deployment для paymentservice 3-х подов в режиме Blue-Green (+3 new, -3 old)  
`kubernetes-controllers/paymentservice-deployment-bg.yaml` -
манифест для разворачивания 3-х подов paymentservice в режиме reverse-rolling (-1 old, +1 new, ...)

###  * Дополнительное 2 (DaemonSet)

`kubernetes-controllers/node-exporter-daemonset.yaml` -
манифест для разворачивания daemon-сервисов с NodeExporter на порту 9100 на всех нодах, включая мастер (для этого использовалась директива tolerations)

```
kubectl port-forward <имя любого pod в DaemonSet> 9100:9100
curl localhost:9100/metrics
```

# 3 (kubernetes-networks) - kind

`kubernetes-networks/web-pod.yaml` - манифест пода с "пробами"  
`kubernetes-networks/web-deploy.yaml` - манифест деплоймента с "пробами" и стратегией развертывания

## Service

`kubernetes-networks/web-svc-cip.yaml` - манифест сервиса типа ClusterIP для приложений web

Установка MetalLB:
```
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.10/config/manifests/metallb-native.yaml
```

`kubernetes-networks/metallb-pool.yaml`  - манифест с пулом адресов для MetalLB. Используется вместо устаревшего ConfigMap  
`kubernetes-networks/web-svc-lb.yaml` - манифест сервиса типа LoadBalancer для приложений web

Добавление статического маршрута в кластер (пул MetalLB):
```
sudo route add -net 172.17.255.0/24 gw 172.18.0.2
```

Проверка LB для сервиса web-svc-lb:
```
curl http://172.17.255.1/
```

###  * Дополнительное (LB for CoreDNS)

`kubernetes-networks/coredns/kube-dns-lb.yaml` - манифест сервиса типа LoadBalancer для приложений kube-dns

Проверка DNS-запроса в Core-DNS по адресу LB:
```
nslookup web-svc.default.svc.cluster.local 172.17.255.2
```
## Ingress

Установка актуальной версии nginx-ingress контроллера:
```
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

`kubernetes-networks/nginx-lb.yaml` - манифест сервиса типа LoadBalancer для ingress-nginx. Уже есть в поставке актуальной версии (ссылку см. выше)  
`kubernetes-networks/web-svc-headless.yaml` - манифест сервиса типа Headless для приложений web  
`kubernetes-networks/web-ingress.yaml` - манифест Ingress для сервиса web-svc

Проверка Ingress для приложений web:
```
curl http://172.17.255.3/web/
```

###  * Дополнительное (K8s-dashboard Ingress)

Dashboard for K8s требует установленых nginx-ingress и cert-manager.

```
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml
```

`kubernetes-networks/dashboard/dashboard-ingress.yaml` - манифест Ingress для сервиса kubernetes-dashboard-web

```
curl http://172.17.255.3/dashboard/
```

###  * Дополнительное (Canary Ingress)

Для этого в Ingress для канареечной версии сервиса используются аннотации:
- *nginx.ingress.kubernetes.io/canary*
- *nginx.ingress.kubernetes.io/canary-by-header*
- *nginx.ingress.kubernetes.io/canary-by-header-value*

`kubernetes-networks/canary/web-deploy-canary.yaml` - манифест c деплойментом приложения новой версии  
`kubernetes-networks/canary/web-svc-headless-canary` - манифест сервиса типа Headless для приложений web-canary  
`kubernetes-networks/canary/web-ingress-canary` - манифест Ingress для проксирования в новую версию по заголовку "alternative=YES"

```
curl http://172.17.255.3/web/ -H "alternative: YES"
```

# 4 (kubernetes-volumes) - kind

## StatefulSet

`kubernetes-volumes/minio-secret.yaml` - манифест Secret для логопаса администратора minIO  
`kubernetes-volumes/minio-statefulset.yaml` - манифест StatefulSet развертыания minIO в одном экземлпяре с персистентной дисковой памятью  
`kubernetes-volumes/minio-headless-service.yaml` - манифест сервиса minio типа Headless для доступа к конкретному экземпляру minIO внутри кластера по известному IP-адресу (из списка адресов *minio.default.svc.cluster.local*) или по имени *minio-{номер экземпляра}.minio.default.svc.cluster.local*

## PersistentVolume

Ниже приведен пример статического выделения дискового пространтсва для работы подов.

`kubernetes-volumes/my-pv.yaml` - манифест PersistentVolume (PV) my-pv, описывающий тип и свойства постоянной дисковой памяти выделенной в кластере. Выделен тип hostPath с размещением в /mnt/data и размером в 1 гибибайт. Приписан storage-класс manual  
`kubernetes-volumes/my-pvc.yaml` - манифест Persistent (PVC) my-pvc для текущего namespace=deafault с требованиями выделения дисковой памяти с определенными свойствами для работы будущих подов. Запрошено пространство в 500 мибибайт и классом manual (иначе будет выделен PV по динамической процедуре из класса default)  
`kubernetes-volumes/my-pod.yaml` - манифест Pod my-pod для использования тома в /app/data, использующего требоваение PVC my-pvc  
`kubernetes-volumes/my-pod-2.yaml` - манифест второго Pod my-pod-2 для использования того же тома с тем же требованием PVC, что и в первом поде  

# 5 (kubernetes-security) - kind

## ServiceAccount / RoleBinding / Role / ClusterRoleBinding / ClusterRole

### Task 1

- Создать Service Account bob , дать ему роль admin в рамках всего
кластера
- Создать Service Account dave без доступа к кластеру


`task-1/01-bob-sa.yaml` - манифест ServiceAccount (SA) для пользователя **bob**  
`task-1/02-crb.yaml` - манифест ClusterRoleBinding выдачи существующей кластерной роли **admin** для SA bob-sa  
`task-1/03-bob-sa-token.yaml` - манифест Secret для токена доступа для SA bob-sa. Нужен для версии k8s 1.24 и выще  

Чтобы проверить через kubectl права у bob-sa, нужно добавить в kubeconfig  необходимые данные:
```
export BOB_TOKEN=`kubectl get secret bob-sa-token -o jsonpath='{.data.token}' | base64 --decode`

kubectl config set-credentials bob --token=$BOB_TOKEN
```

Список всех прав в текущем пространстве имен от текущего пользователя:
```
kubectl auth can-i --list -n default
```
Проверка возможности получения списка подов во всех пространствах имён от пользователя **bob**:
```
kubectl auth can-i list pods -A --user=bob
```
То же самое, но токен доступа указан рядом и повышен уровень логирования:
```
kubectl can-i list pods -A --user=bob --token=$BOB_TOKEN
```

Аналогично - для пользователя **dave**:

`task-1/04-dave-sa.yaml` - манифест ServiceAccount  
`task-1/05-dave-sa-token.yaml` - манифест Secret для токена доступа

### Task 2

*В этой и следующей задачах токен доступа для проверки прав у SA не создавался.
Для проверки прав можно использовать impersonation у суперпользователя:
```
kubectl --v=7 can-i list pods -A --as=system:serviceaccount:default:bob 
```

- Создать Namespace prometheus
- Создать Service Account carol в этом Namespace
- Дать всем Service Account в Namespace prometheus возможность делать
get , list , watch в отношении Pods всего кластера

`task-2/01-prometheus-ns.yaml` - манифест Namespace **prometheus**  
`task-2/02-carol-sa.yaml` - манифест ServiceAccount для пользователя **carol**  
`task-2/03-custom-cluster-role.yaml` - манифест ClusterRole c правами get/list/watch на поды  
`task-2/04-all-crb.yaml` - манифест ClusterRoleBinding выдачи роли custom-cluster-role для всех SA из пространства имен prometheus

### Task 3

- Создать Namespace dev
- Создать Service Account jane в Namespace dev
- Дать jane роль admin в рамках Namespace dev
- Создать Service Account ken в Namespace dev
- Дать ken роль view в рамках Namespace dev


`task-3/01-dev-ns.yaml` - манифест Namespace **dev**  
`task-3/02-jane-sa.yaml` - манифест ServiceAccount для пользователя **jane**  
`task-3/03-jane-rb.yaml` - манифест RoleBinding выдачи кластерной роли **admin** для SA jane  
`task-3/04-ken-sa.yaml` - манифест ServiceAccount для пользователя **ken**  
`task-3/05-ken-rb.yaml` - манифест RoleBinding выдачи кластерной роли **view** для SA ken  

# 5 (kubernetes-templating) - minikube (k8s 1.21.14)

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

Установка необходимых для работы с Let's Encrypt ресурсов k8s для cert-manager (Issuer, ClusterIssuer):
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

https://github.com/helmfile/helmfile - документация

cd kubernetes-templating/helmfile/
helmfile sync  
helmfile apply  
helmfile template  

## * Свой helm-чарт

helm dependency update kubernetes-templating/hipster-shop  
```
helm upgrade --install hipster-shop kubernetes-templating/hipster-shop --namespace hipster-shop --create-namespace
```

### * Дополнительное (chart dependencies)

`kubernetes-templating/hipster-shop/Chart.yaml` - указаны зависимости, в том числе для Redis
`kubernetes-templating/hipster-shop/values.yaml` - настроенные переменные для Redis

## helm-secrets

helm plugin install https://github.com/futuresimple/helm-secrets
gpg --full-generate-key  
gpg -k  
sops -e -i --pgp 9DE1B26A51D0265C475529092FE6BC985112D9E1 kubernetes-templating/frontend/secrets.yaml 

helm secrets upgrade --install frontend kubernetes-templating/frontend --namespace hipster-shop -f kubernetes-templating/frontend/values.yaml -f kubernetes-templating/frontend/secrets.yaml

sops -d -i --pgp 9DE1B26A51D0265C475529092FE6BC985112D9E1 ../../frontend/secrets.yaml

`repo.sh` - helm repo add myrepo https://chartmuseum.dev.ganiev.su 
helm package kubernetes-templating/frontend  
curl -X POST --data-binary "@frontend-0.1.0.tgz" https://chartmuseum.dev.ganiev.su/api/charts 
helm dependency update kubernetes-templating/hipster-shop  

## kubecfg (jsonnet)

paymentservice
shippingservice

helm upgrade --install hipster-shop . --namespace hipster-shop --create-namespace  

go install github.com/kubecfg/kubecfg@latest

Библиотеки libsonnet для шаблонизации манифестов k8s:
 - https://github.com/kube-libsonnet/kube-libsonnet (former bitnami project)
 - https://github.com/jsonnet-libs/k8s-libsonnet

Можно подключить библоитеки несколькими способами, все они предполагаю копирование необходимых файлов
и указание пути до них в импорте шаблона.

Вариант 1: Установка json-bundler (jb) и последующая установка библиотеки libsonnet
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

Использован вариант 1:


kubecfg validate services2.jsonnet
kubecfg update services2.jsonnet --namespace hipster-shop

## * kapitan (jsonnet)

cartservice
helm upgrade --install hipster-shop . --namespace hipster-shop --create-namespace  


kapitan init


kapitan compile
compiled/cartservice/scripts/apply.sh

## kustomize

productcatalogservice
helm upgrade --install hipster-shop . --namespace hipster-shop --create-namespace  