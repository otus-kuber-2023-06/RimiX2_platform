# OTUS k8s-platfrom homework

# 1 (kubernetes-intro)
## Основное

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
## Основное (Deployment / Probes)

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

`web-pod.yaml` - манифест пода с "пробами"  
`web-pod.yaml` - манифест деплоймента с "пробами" и стратегией развертывания

## Service

`web-svc-cip.yaml` - манифест сервиса типа ClusterIP для приложений web

Установка MetalLB:
```
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.10/config/manifests/metallb-native.yaml
```

`metallb-pool.yaml`  - манифест с пулом адресов для MetalLB. Используется вместо устаревшего ConfigMap  
`web-svc-lb.yaml` - манифест сервиса типа LoadBalancer для приложений web

Добавление статического маршрута в кластер (пул MetalLB):
```
sudo route add -net 172.17.255.0/24 gw 172.18.0.2
```

Проверка LB для сервиса web-svc-lb:
```
curl http://172.17.255.1/
```

###  * Дополнительное (LB for CoreDNS)

`coredns/kube-dns-lb.yaml` - манифест сервиса типа LoadBalancer для приложений kube-dns

Проверка DNS-запроса в Core-DNS по адресу LB:
```
nslookup web-svc.default.svc.cluster.local 172.17.255.2
```
## Ingress

Установка актуальной версии nginx-ingress контроллера:
```
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

`nginx-lb.yaml` - манифест сервиса типа LoadBalancer для ingress-nginx. Уже есть в поставке актуальной версии (ссылку см. выше)  
`web-svc-headless.yaml` - манифест сервиса типа Headless для приложений web  
`web-ingress.yaml` - манифест Ingress для сервиса web-svc

Проверка Ingress для приложений web:
```
curl http://172.17.255.3/web/
```

###  * Дополнительное (K8s-dashboard Ingress)

Dashboard for K8s требует установленых nginx-ingress и cert-manager.

```
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml
```

`dashboard/dashboard-ingress.yaml` - манифест Ingress для сервиса kubernetes-dashboard-web

```
curl http://172.17.255.3/dashboard/
```

###  * Дополнительное (Canary Ingress)

Для этого в Ingress для канареечной версии сервиса используются аннотации:
- *nginx.ingress.kubernetes.io/canary*
- *nginx.ingress.kubernetes.io/canary-by-header*
- *nginx.ingress.kubernetes.io/canary-by-header-value*

`canary/web-deploy-canary.yaml` - манифест c деплойментом приложения новой версии  
`canary/web-svc-headless-canary` - манифест сервиса типа Headless для приложений web-canary  
`canary/web-ingress-canary` - манифест Ingress для проксирования в новую версию по заголовку "alternative=YES"

```
curl http://172.17.255.3/web/ -H "alternative: YES"
```