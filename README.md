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

Такая команда выдаст список всех прав в текущем пространстве имен от текущего пользователя:
```
kubectl auth can-i --list -n default
```
Эта - проверит возможность листинга подов во всех пространствах имён от пользователя **bob**:
```
kubectl auth can-i list pods -A --user=bob
```
То же самое, но токен доступа указан рядом:
```
kubectl auth can-i list pods -A --user=bob --token=$BOB_TOKEN
```

Аналогично - для пользователя **dave**:

`task-1/04-dave-sa.yaml` - манифест ServiceAccount  
`task-1/05-dave-sa-token.yaml` - манифест Secret для токена доступа

### Task 2

*В этой и следующей задачах токен доступа для проверки прав у SA не создавался.

- Создать Namespace prometheus
- Создать Service Account carol в этом Namespace
- Дать всем Service Account в Namespace prometheus возможность делать
get , list , watch в отношении Pods всего кластера

`task-2/01-prometheus-ns.yaml` - манифест Namespace **prometheus**  
`task-2/02-carol-sa.yaml` - манифест ServiceAccount для пользователя **carol**  
`task-2/03-custom-role.yaml` - манифест Role для пространства имен prometheus c правами get/list/watch на поды  
`task-2/04-rb.yaml` - манифест RoleBinding выдачи роли custom-role для SA carol-sa

### Task 3

- Создать Namespace dev
- Создать Service Account jane в Namespace dev
- Дать jane роль admin в рамках Namespace dev
- Создать Service Account ken в Namespace dev
- Дать ken роль view в рамках Namespace dev


`task-3/01-dev-ns.yaml` - манифест Namespace **dev**  
`task-3/02-jane-sa.yaml` - манифест ServiceAccount для пользователя **jane**  
`task-3/03-jane-rb.yaml` - манифест RoleBinding выдачи кластерной роли **admin** для SA jane-sa  
`task-3/04-ken-sa.yaml` - манифест ServiceAccount для пользователя **ken**  
`task-3/05-ken-rb.yaml` - манифест RoleBinding выдачи кластерной роли **view** для SA ken-sa  