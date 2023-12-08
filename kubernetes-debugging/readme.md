# (debugging)

## kubectl debug

Под "дебагом" подразумевается мероприятия (операции) с целью выявления проблем внутри диагностируемого контейнера с помощью дополнительных инструментов. Но в связи с тем, что на практике образ контейнера не содержит ничего лишнего (даже пакетного менеджера) кроме файлов для функционирования целевого приложения, в нём нет инструментов (утилит) для диагностики.  

И хотелось бы это сделать без модификации манифестов и тем более перезапуска диагностируемого пода. В настоящий момент такая возможность есть,  и, начиная с версии k8s 1.25, существует встроенная в командную утилиту `kubectl` команда `debug`, которая позволяет присоединить контейнер к уже работающему поду. По сути создается т.н. "эфемерный контейнер" с необходимым образом рядом с отлаживаемым контейнером. Вместе с этим новому контейнеру могут быть доступны все неймспейсы. Таким образом появляется возможность использования необходимых для отладки инструментов. 

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
Также есть возможность запустить под с неймспейсами конкретной ноды, например, когда ssh-доступа к ноде нет:
```
kubectl debug node/[node-name] -it --image=[debugging-tool-image]
```

## iptables-tailer

Иногда при использовании сетевых политик (NetworkPolicy), работающих на сетевом и транспортном (3-4) уровнях, возникает необходимость быстро понимать причину "непрохождения" трафика. Одним из решений является запись в журнал событий пода всех случаев "отбрасывания" пакетов iptables c помощью [kube-iptables-tailer](https://github.com/box/kube-iptables-tailer)
 
[*]

- Исправьте ошибку в нашей сетевой политике, чтобы Netperf снова начал
работать
- Поправьте манифест DaemonSet из репозитория, чтобы в логах
отображались имена Podов, а не их IP-адреса