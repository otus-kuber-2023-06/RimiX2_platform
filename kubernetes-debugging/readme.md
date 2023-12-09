# (debugging)

## kubectl debug

Под "дебагом" подразумевается мероприятия (операции) с целью выявления проблем с диагностируемым контейнером с помощью дополнительных инструментов. Но в связи с тем, что на практике образ контейнера не содержит ничего лишнего (даже пакетного менеджера) кроме файлов для функционирования целевого приложения, в нём нет инструментов (утилит) для диагностики.  

И хотелось бы это сделать без модификации манифестов и тем более перезапуска диагностируемого пода. В настоящий момент такая возможность есть, и, начиная с версии k8s 1.23, через встроенную в командную утилиту `kubectl` команду `debug`, можно присоединить т.н. "эфемерный контейнер" к уже работающему поду. По сути создается дополнительный контейнер с необходимым образом рядом с отлаживаемым контейнером. Вместе с этим новому контейнеру могут быть доступны те же неймспейсы. Таким образом появляется возможность использования необходимых для отладки инструментов. 

```
kubectl debug [pod-name] -it --image=[debugging-tool-image]
```
Где `pod-name` определяет диагностируемый контейнер, а `debugging-tool-image` - инструмент диагностики. 
И уже в запущенном контейнере можно запустить из командной строки утилиту для диагностики.

Например в данном случаев для пода с MySql используется образ для отладки сети (curl, nslookup, tracert, tcpdump и пр.):
```
kubectl debug -it mysql-instance-765549d488-z2vzx --image=wbitt/network-multitool -- sh
```
При этом в поде создастся эфемерный контейнер со всем доступным в выбранном образе инструментарием, и будет запущен shell в присоединенном интерактивном терминале. Этот новый контейнер будет работать до завершения запущенного процесса (shell). 

Существуют дополнительные опции запуска дебаг-контейнера:
- `--target [container_name]` - эфемерному контейнеру в том же поде будет предоставлены все неймспейсы целевого контейнера (через targetContainerName: [c_n]) (Требуется поддержка со стороны Container Runtime)
- `--copy-to` - создаётся копия целевого пода c дополнительным контейнером (уже side-car) со своим образом
- `--share-processes` - используется вместе с `--copy-to`, включает в поде единый pid-неймспейс (через shareProcessNamespace: true)

```
kubectl debug nginx-pod -it --image=alpine --copy-to debug-pod --share-processes
```

### Ограничения 

Есть проблема с использованием инструментов, требующих систменых capablities. Например, при использовании `strace`, т.к. отладочный контейнер не имеет capability SYS_PTRACE.
На текущий момент `kubectl debug` не предоставляет возможности изменять securityContext или VolumeMounts для эфемерного контейнера. Поэтому как обходное решение можно использовать патч через вызов к API кластера для создания у отлаживаемого пода эфемерного контейнера с необходимым перечнем capabilities.
```
kubectl run http-echo --image=hashicorp/http-echo --port=5678

curl --key rpi4b-key.pem --cert rpi4b-cert.pem --cacert rpi4b-ca.pem \
https://192.168.0.20:6443/api/v1/namespaces/default/pods/http-echo/ephemeralcontainers \
-XPATCH -H 'Content-Type: application/strategic-merge-patch+json' -d '
{
    "spec": {
        "ephemeralContainers": [
            {
                "image": "alpine",
                "name": "debug-1",
                "targetContainerName": "http-echo",
                "command":[ "/bin/sh" ],
                "tty":true,
                "stdin": true,
                "securityContext": {
                    "capabilities": {
                        "add": [
                            "SYS_PTRACE"
                        ]
                    }
                }
            }
        ]
    }
}'

kubectl attach -it http-echo -c debug-1

apk add strace
strace -p1
```
Здесь производится применение патча с помощью curl, присоединение к контейнеру-отладчику, установка инструмента strace и его запуск.


Ещё один вариант патча:
```
curl -v -XPATCH -H "Content-Type: application/json-patch+json" \
'http://127.0.0.1:8001/api/v1/namespaces/default/pods/nginx-8f458dc5b-wkvq4/ephemeralcontainers' \
--data-binary @- << EOF
[{
"op": "add", "path": "/spec/ephemeralContainers/-",
"value": {
"command":[ "/bin/sh" ],
"stdin": true, "tty": true,
"image": "nicolaka/netshoot",
"name": "debug-strace",
"securityContext": {"capabilities": {"add": ["SYS_PTRACE"]}},
"targetContainerName": "nginx" }}]
EOF
```

### Диагностика ноды
Также есть возможность запустить под с неймспейсами конкретной ноды, например, когда ssh-доступа к ней нет:
```
kubectl debug node/[node-name] -it --image=[debugging-tool-image]
```
Контейнеру предоставляются все неймспейсы хоста и  его файловая система, которая доступна в контейнере в точке /host.

## Диагностика сетевых политик (журналирование)

Иногда при использовании сетевых политик (NetworkPolicy), работающих на сетевом и транспортном (3-4) уровнях, возникает необходимость быстро понимать причину "непрохождения" трафика. Одним из решений была запись в журнал событий пода всех случаев "отбрасывания" пакетов iptables c помощью [kube-iptables-tailer](https://github.com/box/kube-iptables-tailer).
По сути это конвертер файлового лога в события k8s.

### Установка iptables-tailer

Требуется старая версия k8s - 1.19, в которой ещё не выключен "RefLink Propagation".
Используем старый kind версии [0.17](https://github.com/kubernetes-sigs/kind/releases/download/v0.17.0/kind-windows-amd64) c образом для нод "kindest/node:v1.19.16":
```
kind-old create cluster --config kind-config.yml
```
В каждой worker-ноде должен быть настроен rsyslog c прецизионным форматом времени - строка 35 в конфигурационном файле:
```
apt update
apt install -y rsyslog
sed -i '35 s/^/#/' /etc/rsyslog.conf
systemctl start rsyslog
```

При желании можно перенаправить логи в отдельный файл iptables.log:
```
echo ':msg, contains, "calico-packet: " -/var/log/iptables.log' > /etc/rsyslog.d/10-iptables.conf
echo '& ~' >> /etc/rsyslog.d/iptables.conf
```

В случае воркер-нод на докере необходимо учитывать [ограничение](https://serverfault.com/questions/691730/iptables-log-rule-inside-a-network-namespace) в логировании из других сетевых неймспейсов. На всех нодах c версией Linux ядра не ниже 4.11 можно выполнить:
```
sysctl -w net.netfilter.nf_log_all_netns=1
```

Устанавливаем CNI в кластер от Calico:
```
kubectl create -f https://docs.projectcalico.org/archive/v3.19/manifests/tigera-operator.yaml
kubectl create -f https://docs.projectcalico.org/archive/v3.19/manifests/custom-resources.yaml
kubectl get pods -l k8s-app=calico-node -n calico-system
```

```
kubectl apply -f tailer-daemonset.yaml
```

### Тест журналирования на примере подов оператора Netperf

Установим оператор:
```
kubectl -f apply deploy/crd.yaml
kubectl -f apply deploy/rbac.yaml
kubectl -f apply deploy/operator.yaml
```


Запустим тест пропускной способности между подами:

```
kubectl -f apply deploy/cr.yaml
```

Т.к. никакой сетевой политики, запрещающей трафик внутри того же неймспейса что и поды оператора (клиент и сервер) нет, тест успешно проводится:
```
kubectl describe netperf/example | tail -n 6
Status:
  Client Pod:          netperf-client-g9dd3166050a
  Server Pod:          netperf-server-g9dd3166050a
  Speed Bits Per Sec:  9254.22
  Status:              Done
Events:                <none>
```

Создадим сетевую политику запрещающий любой трафик внутри неймспейса и перезапустим тест:
```
kubectl -f delete deploy/cr.yaml
kubectl -f apply deploy/cr.yaml
kubectl describe netperf/example | tail -n 6
kubectl -f apply net-policy-calico-deny-all.yaml
Status:
  Client Pod:          netperf-client-616ebca905a4
  Server Pod:          netperf-server-616ebca905a4
  Speed Bits Per Sec:  0
  Status:              Started test
Events:                <none>
```
Видим в событиях клиентского и серверного подов записи об отброшенных пакетах:
```
kubectl get events --sort-by='.metadata.creationTimestamp'
15s         Warning   PacketDrop   pod/netperf-client-b9cb4161059f   Packet dropped when sending traffic to default (192.168.110.144)
15s         Warning   PacketDrop   pod/netperf-server-b9cb4161059f   Packet dropped when receiving traffic from default (192.168.162.147)
```

Применим новую сетевую политику с высшим приоритетом, разрешающую трафик для проведения тестирования с помощью подов оператора Netperf:
```
kubectl -f apply net-policy-calico-allow-netperf.yaml
```
Тест снова проходит успешно:
```
kubectl -f delete deploy/cr.yaml
kubectl -f apply deploy/cr.yaml
kubectl describe netperf/example | tail -n 6
Status:
  Client Pod:          netperf-client-b9cb4161059f
  Server Pod:          netperf-server-b9cb4161059f
  Speed Bits Per Sec:  9053.07
  Status:              Done
Events:                <none>
```