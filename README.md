# OTUS k8s-platfrom homework

# 1 (kubernetes-intro)
## Основное

В результате удаления всех контейнеров через docker или подов через kubectl все они восстановились. Потому что за многими из них следит сервис "kubelet" на ноде (т.н. статические поды), а за динамическими - контроллер репликации.

`kubernetes-intro/web/Dockerfile`
Файл для сборки образа с простым http-сервером и кастомным конфигом

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
Появляется возможность откатывать через CI/CD 
```
kubectl rollout undo deployment/frontend
```
по результату получения
```
kubectl rollout status deployment/frontend --timeout=60s
```
###  * Дополнительное 1 (MaxUnavailable и MaxSurge)

`kubernetes-controllers/paymentservice-deployment-bg.yaml`
Манифест для обновления deployment для paymentservice 3-х подов в режиме Blue-Green (+3 new, -3 old)

`kubernetes-controllers/paymentservice-deployment-bg.yaml`
Манифест для разворачивания 3-х подов paymentservice в режиме reverse-rolling (-1 old, +1 new, ...)

###  * Дополнительное 2 (DaemonSet)

`kubernetes-controllers/node-exporter-daemonset.yaml`
Манифест для разворачивания daemon-сервисов с NodeExporter на порту 9100 на всех нодах, включая мастер (для этого использовалась директива tolerations)

```
kubectl port-forward <имя любого pod в DaemonSet> 9100:9100
curl localhost:9100/metrics
```


