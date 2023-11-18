#7 kubernetes-vault

https://cdn.otus.ru/media/public/86/55/kuber_vault_homeworks_23186_fcda9c_189691_e05a44_5522_0b3422_2-139042-8655c9.pdf

## Установка из официального helm-репозитория серверов Consul и Vault

Consul используется как бэкенд хранения секретов и поддержки работы Vault в кластере (HA)  
`helm repo add hashicorp https://helm.releases.hashicorp.com`  
`helm repo update`  

`helm install consul hashicorp/consul --create-namespace -n consul --values consul/values.yml`
`helm install vault hashicorp/vault --create-namespace -n vault --values vault/values.yml`  

## Распечатывание (unseal)
Инициализация сервера и мастер-ключа для формирования секретного ключа.
Для простоты мастер-ключ делим (key-shares) всего на 1 часть и для распечатывания (key-threshold aka quorum) нужен 1. Обычно задают 7 частей и 3 любых из них для распечатывания.  
`kubectl exec vault-0 -n vault -- vault operator init -key-shares=1 -key-threshold=1 -format=json`
```
{
  "unseal_keys_b64": [
    "PyOOoxQOYaCCgP/YVUoVVcYFzuuWfGOV0JKZgi5Bako="
  ],
  "unseal_keys_hex": [
    "3f238ea3140e61a08280ffd8554a1555c605ceeb967c6395d09299822e416a4a"
  ],
  "unseal_shares": 1,
  "unseal_threshold": 1,
  "recovery_keys_b64": [],
  "recovery_keys_hex": [],
  "recovery_keys_shares": 0,
  "recovery_keys_threshold": 0,
  "root_token": "hvs.mzJzjaW9sP6fWMBEIx6Vhuqi"
}
```
Формированиe секретного ключа (на котором шифруются секреты в бэкенде). Следующие команды повторяем на всех нодах Vault (начинаем с vault-0)

- `kubectl exec -it vault-0 -n vault -- vault operator unseal` - вводим значение из **unseal_keys_b64** или **unseal_keys_hex**  
- `kubectl exec vault-0 -n vault -- vault status` - смотрим, чтобы значение "Sealed" стало "false"
```
Key             Value
---             -----
Seal Type       shamir
Initialized     true
Sealed          false
Total Shares    1
Threshold       1
Version         1.15.1
Build Date      2023-10-20T19:16:11Z
Storage Type    consul
Cluster Name    vault-cluster-244c5e9d
Cluster ID      e8a03d9b-34af-f8cf-7ec6-3c2c8ca3d314
HA Enabled      true
HA Cluster      https://vault-0.vault-internal:8201
HA Mode         active
Active Since    2023-11-14T15:44:33.760536567Z
```

## Работа с CLI

`kubectl exec -it vault-0 -n vault -- vault login` - Создание рут-токена в домашней директории для обращения к API сервера. Вводим значение из **root_token**. 
```
Success! You are now authenticated. The token information displayed below
is already stored in the token helper. You do NOT need to run "vault login"
again. Future Vault requests will automatically use this token.

Key                  Value
---                  -----
token                hvs.mzJzjaW9sP6fWMBEIx6Vhuqi
token_accessor       HZkMyPgfH6zFpRXhHadG4YIw
token_duration       ∞
token_renewable      false
token_policies       ["root"]
identity_policies    []
policies             ["root"]
```


`kubectl exec -it vault-0 -n vault -- vault auth list` - Получение списка включенных на сервере методов аутентификации
```
Path      Type     Accessor               Description                Version
----      ----     --------               -----------                -------
token/    token    auth_token_34abe3f4    token based credentials    n/a
```

### Создание тестовых секретов
`kubectl exec -it vault-0 -n vault -- vault secrets enable --path=otus kv`  - Включение модуля секретов типа KV (v1) (key-value) по пути "otus/*"
`kubectl exec -it vault-0 -n vault -- vault secrets list` - Получение списка включенных на сервере модулей секретов
```
Path          Type         Accessor              Description
----          ----         --------              -----------
cubbyhole/    cubbyhole    cubbyhole_5e465264    per-token private secret storage
identity/     identity     identity_1203915a     identity store
otus/         kv           kv_bce2aec5           n/a
sys/          system       system_d193baac       system endpoints used for control, policy and debugging
```
`kubectl exec -it vault-0 -n vault -- vault kv put otus/otus-ro/config username='otus' password='asajkjkahs'`  
`kubectl exec -it vault-0 -n vault -- vault kv put otus/otus-rw/config username='otus' password='Asajkjkahs'`  
`kubectl exec -it vault-0 -n vault -- vault kv get otus/otus-rw/config`  
```
====== Data ======
Key         Value
---         -----
password    Asajkjkahs
username    otus
```

## Настройка kubernetes-аутентификации


`kubectl exec -it vault-0 -n vault -- vault auth enable kubernetes` - Добавление метода  
`kubectl exec -it vault-0 -n vault -- vault auth list` - Вывод списка активированных методов  
```
Path           Type          Accessor                    Description                Version
----           ----          --------                    -----------                -------
kubernetes/    kubernetes    auth_kubernetes_252859d2    n/a                        n/a
token/         token         auth_token_1cbd2ddb         token based credentials    n/a
```

#### Примечание: 
C версии 1.24 в kubernetes отключена автогенерация секретов при создании ServiceAccount'ов.
Поэтому необходимо создавать дополнительно к ServiceAccount'у секрет вида:
```
apiVersion: v1
kind: Secret
metadata:
  name: sa-name-token
  namespace: ns-name
  annotations:
    kubernetes.io/service-account.name: sa-name
type: kubernetes.io/service-account-token
```

Чтобы сервер Vault'а мог проверять валидность ServiceAccount (используя TokenReview API), нужно, чтобы ServiceAccount (точнее, секрет из него), который он будет использовать, имел права кластерной роли `system:auth-delegator` (уполномочена создавать ресурсы TokenReview).

Приложения в кластере смогут обращаться к Vault за секретами, используя опосредованно (для получения токена доступа) JWT из секрета своего ServiceAccount'а после проверки валидности.

### Конфигурация

После установки из Helm-чарта остался созданный ServiceAccount с именем "vault". 
Он уже привязан к кластерной роли system:auth-delegator через ClusterRoleBinding "vault-server-binding", который тоже остался после установки. Нужно только создать недостающий секрет (см. Примечание), если вы не указали в переменной helm-чарта значение .
```
apiVersion: v1
kind: Secret
metadata:
  name: vault-token
  namespace: vault
  labels:
    app.kubernetes.io/managed-by: Helm
  annotations:
    meta.helm.sh/release-name: vault
    meta.helm.sh/release-namespace: vault
    kubernetes.io/service-account.name: vault
type: kubernetes.io/service-account-token
```

Также серверу Vault необходимо знать адрес API-сервера кластера и его публичный сертификат для TLS-соединения.
Подготовим переменные для конфигурации:
```
export SA_JWT_TOKEN=$(kubectl get secret vault-token -n vault -o jsonpath="{.data.token}" | base64 --decode; echo)
export SA_CA_CRT=$(kubectl get secret vault-token -n vault -o jsonpath="{.data['ca\.crt']}" | base64 --decode; echo)
export K8S_HOST=$(kubectl config view --raw --minify --flatten --output 'jsonpath={.clusters[].cluster.server}')
```

Вносим конфигурацию в Vault-сервер (vault-0):
```
kubectl exec -it vault-0 -n vault -- vault write auth/kubernetes/config \
     token_reviewer_jwt="$SA_JWT_TOKEN" \
     kubernetes_ca_cert="$SA_CA_CRT" \
     kubernetes_host="$K8S_HOST"
```

Создаем роль "otus" для тестового ServiceAccount'a "testing-vault-sa" c политикой, указывая имя привязываемых сервис-аккаунтов и пространств имен:
```
kubectl exec -it vault-0 -n vault -- vault write auth/kubernetes/role/otus \
bound_service_account_names=testing-vault-sa \
bound_service_account_namespaces=default policies=otus-policy ttl=24h
```

Создаём локально ACL-политику "otus-policy" для созданных ранее тестовых секретов, затем копируем их на vault-0 (/tmp) и применяем:
```
tee otus-policy.hcl <<EOF
path "otus/otus-ro/*" {
capabilities = ["read", "list"]
}
path "otus/otus-rw/*" {
capabilities = ["read", "create", "list"]
}
EOF
kubectl cp otus-policy.hcl -n vault vault-0:/tmp/
kubectl exec -it vault-0 -n vault -- vault policy write otus-policy /tmp/otus-policy.hcl
```

### Проверка получения приложением в kubernetes секретов из Vault

Создаем тестовый ServiceAccount:  
`kubectl create sa testing-vault-sa`

Создаем тестовый под c тестовым ServiceAccount'ом "testing-vault-sa" для эмуляции процесса получения секретов подом (приложением)
```
apiVersion: v1
kind: Pod
metadata:
  name: testing-vault
  namespace: default
spec:
  serviceAccountName: testing-vault-sa
  containers:
    - name: testing-vault
      image: alpine
      command: ["sh","-c","sleep infinity"]
```
Внутри пода выполняем:
```
apk add curl jq
VAULT_ADDR=http://vault.vault:8200
KUBE_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
ACCESS_TOKEN=$(curl -s -XPOST --data '{"jwt": "'$KUBE_TOKEN'", "role": "otus"}' $VAULT_ADDR/v1/auth/kubernetes/login | jq -r '.auth.client_token')
curl --header "X-Vault-Token:$ACCESS_TOKEN" $VAULT_ADDR/v1/otus/otus-ro/config
curl --header "X-Vault-Token:$ACCESS_TOKEN" $VAULT_ADDR/v1/otus/otus-rw/config
curl -XPOST --data '{"bar": "baz"}' --header "X-Vault-Token:$ACCESS_TOKEN" $VAULT_ADDR/v1/otus/otus-ro/config
curl -XPOST --data '{"bar": "baz"}' --header "X-Vault-Token:$ACCESS_TOKEN" $VAULT_ADDR/v1/otus/otus-rw/config
curl -XPOST --data '{"bar": "baz"}' --header "X-Vault-Token:$ACCESS_TOKEN" $VAULT_ADDR/v1/otus/otus-rw/config1
```

Согласно установленной раннее политике "otus-policy":
- в "otus/otus-ro/" разрешены только чтение и перечисление
- в "otus/otus-rw/" разрешены чтение, перечисление и создание

Поэтому чтобы произвести обновление секрета (перезапись) в "otus/otus-rw/config", нужно добавить в полититку для "otus/otus-rw/" право "update".

## Использование агента Vault
`git clone https://github.com/hashicorp/vault-guides.git` - официальный репозиторий с примерами использования 
`cd vault-guides/identity/vault-agent-k8s-demo && git checkout 65114fb9507a447d4c7ef4a533328d452b77177f` - пример с Vault Agent/Consul Template/Nginx

В примере демонстрируется генерация страницы для Nginx с включенными в неё секретами из Vault.
Контейнер vault в режиме autoauth выполняет login в сервер Vault, содержащим необходимые секреты. Сохраняет токен доступа в общий volume "vault-token" в оперативной памяти.
Контейнер c consul-template, используя общий volume c полученным токеном доступа, получает необходимые для шаблона страницы секретные значения и сохраняет сгенерированную страницу в общий volume "shared-data" для Nginx на диск.
Клиент обращается к контейнеру nginx за страницей и получает её вместе с секретными значениями.
#### Примечание:
C версии 1.3 Vault позволяет обходиться без Consul-Template: добавлена поддержка темплейтирования на языке Consul Template markup.

Копируем из репозитория и подготавливаем следующие файлы:  
`agent-usecase/configs-k8s/consul-template-config.hcl` - конфиг в формате "HashiCorp configuration language" для контейнера с **Consul Template**   
`agent-usecase/configs-k8s/vault-agent-config.hcl` - конфиг для контейнера с **Vault**  
`agent-usecase/example-k8s-spec.yml` - манифест тестового пода c контейнерами (vault/consul-template/nginx)  

Cоздаём ConfigMap для тестового пода:  
```
kubectl create configmap example-vault-agent-config --from-file=./configs-k8s/
kubectl get configmap example-vault-agent-config -o yaml
```

Создаем тестовый под:  
```
kubectl apply -f example-k8s-spec.yml
```  

Заходим в контейнер nginx и получаем содержимое сгенерированной страницы:
```
root@vault-agent-example:/# cat /usr/share/nginx/html/index.html
  <html>
  <body>
  <p>Some secrets:</p>
  <ul>
  <li><pre>username: otus</pre></li>
  <li><pre>password: asajkjkahs</pre></li>
  </ul>

  </body>
  </html>
```

---
## Использование модуля PKI для создания Root/Intermediate/Leaf сертификатов

### Корневой CA
`kubectl exec -it vault-0 -n vault -- vault secrets enable --path=pki-root pki` - включение модуля секретов типа PKI по пути "pki-root" для корневого СА  
`kubectl exec -it vault-0 -n vault -- vault read sys/mounts/pki-root/tune` - просмотр текущих установок модуля
`kubectl exec -it vault-0 -n vault -- vault secrets tune -max-lease-ttl=87600h pki-root` - установка максимального времени жизни токенов и секретов (сроков сертификатов) модуля до 10 лет

`kubectl exec -it vault-0 -m vault -- vault write -field=certificate pki-root/root/generate/internal common_name="example-ca.ru" ttl=87600h > root-cert.pem` - генерация самоподписанного корневого сертификата и создание издателя (issuer). Вывод не содержит (опция internal) приватный ключ сертификата, только сам сертификат, который сохраняется в локальный файл. Приватный ключ вместе с сертификатом безусловно записываются в бэкенд. 

`kubectl exec -it vault-0 -n vault -- vault write pki-root/config/urls issuing_certificates="http://vault.vault:8200/v1/pki-root/ca" crl_distribution_points="http://vault.vault:8200/v1/pki-root/crl"` - установка URL'ов до CA (сертификата в формате DER) и СRL (списка отзыва в формате DER), которые будут указываться в выпускаемых промежуточных сертификатах 

### Промежуточный CA

`kubectl exec -it vault-0 -n vault -- vault secrets enable --path=pki-int pki` - включение модуля секретов типа PKI по пути "pki-int" для промежуточного СА  
`kubectl exec -it vault-0 -n vault -- vault secrets tune -max-lease-ttl=87600h pki-int` - установка максимального времени жизни токенов и секретов (сроков сертификатов) модуля  
`kubectl exec -it vault-0 -n vault -- vault write -format=json pki-int/intermediate/generate/internal common_name="example-ca.ru  Intermediate Authority" | jq -r '.data.csr' > pki-int.csr` - генерация запроса на сертификат с сохранением его в локальный файл

`kubectl cp pki-int.csr -n vault vault-0:./tmp/` - копирование файла запроса на сервер  
`kubectl exec -it vault-0 -n vault -- vault write -format=json pki-root/root/sign-intermediate csr=@/tmp/pki-int.csr format=pem_bundle ttl="43800h" | jq -r '.data.certificate' > intermediate_cert.pem` - подписание промежуточного сертификата на 5 лет корневым сертификатом по переданному запросу с сохранением полученного сертификата в локальный файл в формате PEM вместе с корневым
`kubectl cp intermediate_cert.pem -n vault vault-0:./tmp/` - копирование файла на сервер  
`kubectl exec -it vault-0 -n vault -- vault write pki-int/intermediate/set-signed certificate=@/tmp/intermediate_cert.pem` - установка сертификата и создание издателя  
`kubectl exec -it vault-0 -n vault -- vault write pki-int/config/urls issuing_certificates="http://vault.vault:8200/v1/pki-int/ca" crl_distribution_points="http://vault.vault:8200/v1/pki-int/crl"` - установка URL'ов до CA (сертификата в формате DER) и СRL (списка отзыва в формате DER), которые будут указываться в выпускаемых промежуточных сертификатах 

`kubectl exec -it vault-0 -n vault -- vault write pki-int/roles/example-dot-ru allowed_domains="example.ru" allow_subdomains=true max_ttl="720h"` - создание роли "example-dot-ru" для выпуска сертификатов домена и субдоменов "example.ru"

`kubectl exec -it vault-0 -n vault -- vault write pki-int/issue/example-dot-ru common_name="testing.example.ru" ttl="24h"` - выпуск сертификата под ролью example-dot-ru для домена 3-го уровня testing.example.ru со сроком 1 день
```
Key                 Value
---                 -----
ca_chain            [-----BEGIN CERTIFICATE-----
MIIDuTCCAqGgAwIBAgIUcZxD0IrG312D1A6fAuayW9U2OwMwDQYJKoZIhvcNAQEL
...обрезано..
yRv/8T3eaPuB1wONIEXf0JlYKbz9QGyrBVtybr4IE+BNvT5KSw4EkrAzvWVt
-----END CERTIFICATE----- -----BEGIN CERTIFICATE-----
MIIDOzCCAiOgAwIBAgIUKdl/ImJEFCG10HzHC5ovqlDMnsUwDQYJKoZIhvcNAQEL
...обрезано..
7CkYrU2Kkn3V/pZR3UR4
-----END CERTIFICATE-----]
certificate         -----BEGIN CERTIFICATE-----
MIID6zCCAtOgAwIBAgIUdE/LKnyRbTrRYof2JFBq16PACTUwDQYJKoZIhvcNAQEL
...обрезано..
LGlDgZRoeRG4Y0Fg3ialvI5IgibXwrmZaKT3yTOoX83T/uazuJ4EhgqaTooDOBA=
-----END CERTIFICATE-----
expiration          1700395588
issuing_ca          -----BEGIN CERTIFICATE-----
MIIDuTCCAqGgAwIBAgIUcZxD0IrG312D1A6fAuayW9U2OwMwDQYJKoZIhvcNAQEL
...обрезано..
yRv/8T3eaPuB1wONIEXf0JlYKbz9QGyrBVtybr4IE+BNvT5KSw4EkrAzvWVt
-----END CERTIFICATE-----
private_key         -----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAmmd1GLq7EntH3AuxILGqResijK0u3An6fjrXd1W+9E/Kn0ch
...обрезано..
qDwJdYPkgicVJXBc79CqxEQA3NuEAISlxFMvbxAVUb+xZ3/IhQ4=
-----END RSA PRIVATE KEY-----
private_key_type    rsa
serial_number       74:4f:cb:2a:7c:91:6d:3a:d1:62:87:f6:24:50:6a:d7:a3:c0:09:35
```

`kubectl exec -it vault-0 -n vault -- vault write pki-int/revoke serial_number="74:4f:cb:2a:7c:91:6d:3a:d1:62:87:f6:24:50:6a:d7:a3:c0:09:35"` - отзыв сертификата с определенным серийным номером  

Проверка списка CRL промежуточного СA:
```
curl http://vault.vault:8200/v1/pki-int/crl --output crl.der
openssl crl -inform DER -text -in crl.der
```

## (*) Настройка одностороннего TLS для сервера Vault

Общие способы настройки TLS:
- настройка Ingress с TLS (работает только для внешних обращений)
- настройка слушателя непосредственно на самом сервере 

Будем настраивать без использования Ingress, т.е. сам сервер.
Для настройки сервера необходимо:
- создать или получить где-то пару ассиметричных ключей - server.key и server.pem  
- занести эти файлы на диск сервера, чтобы они были доступны ему локально
- внести изменения в конфигурационный файл Vault'a
- перезапустить сервер и распечатать сервер

Параметры в блоке конфигурации, которые настраивают одностороний TLS:

```
...
listener "tcp" {
...
  tls_disable = 0
  tls_cert_file = "path/cert.pem"
  tls_key_file  = "path/key.pem"
  tls_require_and_verify_client_cert = 0
  # tls_client_ca_file = "path/ca.pem"
...
}
...
```
Возможные способы для Vault'а, развернутого в кластере k8s:
- обновление (или патч) действующих манифестов через kubectl (statefullset, configmap)
- обновление релиза через helm с использованием переопределяемых переменных, предоставляемых чартом  (global.tlsDisable, server.volumes\volumeMounts и server.ha.config)

Оба способа так или иначе требует наличия файлов (ключа и сертификата), заранее доступных в неймспейсе, в котором работает Vault-сервер. Поэтому создадим секреты с ними:
```
kubectl create secret tls -n vault test-tls --key="tls/key.pem" --cert="tls/server.pem"
```

Т.к. установка Vault был произведена через helm, будем обновлять релиз с новыми переопределяемыми переменными:
```
helm upgrade -n vault vault hashicorp/vault -f vault/tls/values.yml
```
Перезапуск серверов:
```
kubectl scale statefulsets vault -n vault --replicas=0
kubectl scale statefulsets vault -n vault --replicas=3
```

При распечатывании и вообще работе с Vault CLI может понадобится ключ "-tls-skip-verify"

## (*) Настройка autounseal

Vault позволяет автоматизировать распечатывание узлов. Для этого части ключей должны быть доступны на внешних "провайдерах".
Это полезно в случае
Процесс 
Провайдер Vault Transit

## (*) Использование динамических секретов для СУБД

Для начала необходимо создать роль "ro" на стороне СУБД с необходимыми правами:
```
CREATE ROLE ro NOINHERIT;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "ro";
```
И включить модуль работы с различными СУБД:
```
vault secrets enable database
```

Настраиваем плагин работы с Postgresql для модуля. Создаем конфигурацию с именем "posgresql":
```
vault write database/config/postgresql \
    plugin_name=postgresql-database-plugin \
    connection_url="postgresql://{{username}}:{{password}}@192.168.0.4:5432/postgres?sslmode=disable" \
    allowed_roles=readonly \
    username="root" \
    password="rootpassword"
```
Создаем sql-файл с запросами на создание учётной записи в СУБД. Значения в {{}} будут предоставления во время исполнения Vault'ом:
```
CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}' INHERIT;
GRANT ro TO "{{name}}";
```

Создаем роль "readonly" в модуле:
```
vault write database/roles/readonly \
    db_name=postgresql \
    creation_statements=@readonly.sql \
    default_ttl=1h \
    max_ttl=24h
```

Политика для роли:
```
path "database/creds/readonly" {
  capabilities = [ "read" ]
}
```
Приложение, которое захочет получить временные реквизиты доступа к СУБД должно сначала успешно авторизоваться в Vault и, согласно
созданной заранее для приложения политики ACL, получить секреты по пути "database/creds/readonly":
```
vault read database/creds/readonly
Key                Value
---                -----
lease_id           database/creds/readonly/uOqsNxc3STmGcA4rcUHoIZfo
lease_duration     1h
lease_renewable    true
password           htYIB3lE9C7pb1G-XR6w
username           v-userpass-readonly-AoBUrODEGJOkL1NXK9M4-1700317224
```
`vault list sys/leases/lookup/database/creds/readonly` - просмотр выданных lease'ов доступа к СУБД для роли "readonly"