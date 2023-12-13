# Установка/обновление кластера (on-premise)

Методы установки:
- "Hard Way" - полностью ручная установка и настройка необходимых бинарных, конфигурационных и других файлов 
- Автоматизированная установка c помощью инструментов kubespray/kubeadm/kops

Обновлять кластер с помощью того же метода и инструмента, что был использован при изначальной установке.
Подходы к обновлению:
- Замена всего кластера целиком на новый (Blue/Green). Без риска, с возможностью отката. Требуется: 
    - дополнительное такое же количество вычислительных ресурсов (хостов)
    - маршрутизация части трафика через GLSB
    - сетевые доступы для разделяемых внешних сервисов
    - перенос ресурсов (манифестов, хранилищ с данными) с рабочей нагрузкой
- Замена узла на новый (RollingUpdate) - без риска, с возможностью отката
- Обновление каждого узла (с запретом планирования/выведением нагрузки на другую ноду) - есть риск, сложность отката

## Установка версии 1.23 с помощью kubeadm 

### Конфигурация кластера:
- 1 master-нода и 3 worker-ноды (2xCPU / 4GB RAM / 20GB STORAGE)
- Внутрикластерный etcd
- CRI - containerd
- CNI - Flannel
- OS - Ubuntu 18.04
- подсеть /28

### Мастер нода (Control Plane)
1. Установить конфигурацию SELinux (при наличии):
```
sudo setenforce 0
sudo sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config
```
2. Выключить swap (при наличии):
```
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
sudo swapoff -a
```
3. Установить и загрузить необходимые модули в ядро:
```
cat <<EOF | sudo tee /etc/modules-load.d/containerd.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter
```
4. Настройть системные параметры ядра и применить их:
```
sudo tee /etc/sysctl.d/kubernetes.conf<<EOF
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
net/bridge/bridge-nf-call-arptables = 1
net.ipv4.ip_forward = 1
EOF
sudo sysctl --system
```
5. Установить с помощью пакетного менеджера и запустить `containerd`:
```
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update -y
sudo apt install -y containerd.io
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```
6. Установить с помощью пакетного менеджера `kubeadm`, `kubectl` и `kubelet`:
```
sudo apt-get update && sudo apt-get install -y apt-transport-https curl
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo echo "deb https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt update -y
sudo apt -y install vim git curl wget kubelet=1.23.0-00 kubeadm=1.23.0-00 kubectl=1.23.0-00
sudo apt-mark hold kubelet kubeadm kubectl
```
7. Предварительно загрузить необходимые образы для компонентов:
```
sudo kubeadm config images pull --cri-socket /run/containerd/containerd.sock --kubernetes-version v1.23.0
```
8. Инициализировать кластер и установить компоненты ядра:
```
sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --upload-certs --kubernetes-version=v1.23.0 --ignore-preflight-errors=Mem  --cri-socket /run/containerd/containerd.sock
```
9. Установить сетевой плагин Flannel:
```
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/v0.17.0/Documentation/kube-flannel.yml
```
10. Скопировать "kubeconfig" в домашнюю директорию пользователя:
```
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

### Рабочие узлы (worker)

Если были утеряны данные (токен и хэш сертификата), полученные при инициализации, то можно их восстановить:
```
sudo kubeadm token list
openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* //'
```
Добавление рабочего узла в кластер:
``` 
sudo kubeadm join 192.168.0.5:6443 --token 407c28.kzqtakqmxc4ri40l \
        --discovery-token-ca-cert-hash sha256:313449f617fa1de378564ef80e0161d65ab707ff126a406f29f0aff5adbc85d5
```

### Получившийся результат

```
$ kubectl get nodes -o wide
NAME      STATUS   ROLES           AGE   VERSION    INTERNAL-IP    EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION      CONTAINER-RUNTIME
master0   Ready    control-plane   2h   v1.23.00   192.168.0.5    <none>        Ubuntu 20.04.6 LTS   5.4.0-167-generic   containerd://1.6.26
worker0   Ready    <none>          2h   v1.23.00   192.168.0.12   <none>        Ubuntu 20.04.6 LTS   5.4.0-167-generic   containerd://1.6.26
worker1   Ready    <none>          2h   v1.23.00   192.168.0.17   <none>        Ubuntu 20.04.6 LTS   5.4.0-167-generic   containerd://1.6.26
worker2   Ready    <none>          1h   v1.23.00   192.168.0.21   <none>        Ubuntu 20.04.6 LTS   5.4.0-167-generic   containerd://1.6.26
```

## Обновление того же кластера до версии 1.24 с помощю kubeadm

Перед обновлением нужно всегда делать резервную копию кластера, используя инструменты
`velero` и `etcdctl snapshot`.

Применим 3-й подход со стратегий RollingUpdate. Будем обновлять каждый узел по порядку, начиная с узлов Control Plane (роль мастера). Выполняем для каждой ноды:

1. Обновить репозитории пакетного менеджера и показать какие версии kubeadm 1.24 в каких репозиториях есть:
```
sudo apt update && sudo apt-cache madison kubeadm
```
2. Обновить через пакетный менеджер утилиту kubeadm до версии 1.24.17:
```
sudo apt-mark unhold kubeadm && sudo apt-get install -y kubeadm=1.24.17-00 && sudo apt-mark hold kubeadm
```
3. Посмотреть план обновления (только для узлов Control Plane)
```
sudo kubeadm upgrade plan
```
4. Применить обновление компонентов ядра (etcd, api-server, kube-proxy, scheduler, controller-manager)(только для узлов Control Plane):
```
sudo kubeadm upgrade apply v1.24.17
```
5. Применить обновление для конфигурации ноды:
```
sudo kubeadm upgrade node
```
6. Установить запрет на планирование нагрузки на ноде (в случае отсутствия другой ноды той же роли)
```
kubectl cordon [node_name]
```
7. Вывести нагрузку и установить запрет на её планирование на ноде (в случае наличия другой ноды той же роли):
```
kubectl drain [node_name] --ignore-daemonsets
```
8. Обновить через пакетный менеджер kubelet и kubectl до версии 1.24.17 и перезагрузить сервис kubelet:
```
sudo apt-mark unhold kubelet kubectl && sudo apt-get install -y kubelet=1.24.17-00 kubectl=1.24.17-00 && sudo apt-mark hold kubelet kubectl
sudo systemctl daemon-reload && sudo systemctl restart kubelet
```
9. Вернуть в строй ноду (снять запрет на планирование нагрузки с ноды):
``` 
kubectl uncordon [node_name]
```
10. Обновить сетевой плагин Flannel:
```
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/v0.18.0/Documentation/kube-flannel.yml
``` 

Получившийся результат:
```
$ kubectl get nodes
NAME      STATUS   ROLES           AGE   VERSION
master0   Ready    control-plane   25h   v1.24.17
worker0   Ready    <none>          24h   v1.24.17
worker1   Ready    <none>          24h   v1.24.17
worker2   Ready    <none>          24h   v1.24.17
```

## Установка с помощью kubespray

Инструмент `kubespray` - это Ansible плейбук. Он запускается на не-Windows машине с установленным Python3, pip и venv. С неё требуется SSH-доступ по ключу пользователя c правом безпарольного SUDO на суперпользовательский (root) шелл до подготовленных к установке хостов.

Подготовка к использованию инструмента:
```
git clone https://github.com/kubernetes-sigs/kubespray.git
cd kubespray
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt 
cp -rfp inventory/sample inventory/mycluster
```
 В инвентарный файл "inventory.ini" заносятся необходимые адреса мастеров и рабочих узлов:
 ```
 vi inventory/mycluster/inventory.ini
 ``` 

При необходимости переменные для кастомизированной установки кластера записываются через опцию -e. Запускается плейбук "cluster.yml" на установку: 
```
ansible-playbook -i inventory/mycluster/inventory.ini --become --user=${SSH_USERNAME} --key-file=${SSH_PRIVATE_KEY} cluster.yml
``` 

Для обновления или удаления кластера есть отдельные плейбуки (upgrade-cluster.yml/reset.yml) в том же репозитории kubespray.

## (*) Установка последней стабильной версии с помощью kubeadm
Конфигурация кластера:
- подсеть /28
- 3 master-ноды (2xCPU, 4xRAM, 15GB) и 2 worker-ноды (2xCPU, 4xRAM, 30GB)
- OS - debian 12
- Внутрикластерный etcd
- CRI - cri-o
- CNI - calico
- Ingress-контроллер Nginx
- внешний IP для единой точки к API кластера (HA/LB)

Setup:
- 5 (3 master + 2 worker) VM/Bare metal (2xCPU, 4xRAM, 30GB) with unique machine IDs (/sys/class/dmi/id/product_uuid, interface's MAC address)
- network connectivity
- OS (debian 12)
    - apt update
- hostname
- ssh keys
- swap off
- container runtime (cri-o) 
  -  echo "deb [signed-by=/usr/share/keyrings/libcontainers-archive-keyring.gpg] https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/$OS/ /" > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
  -  echo "deb [signed-by=/usr/share/keyrings/libcontainers-crio-archive-keyring.gpg] https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable:/cri-o:/$VERSION/$OS/ /" > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable:cri-o:$VERSION.list
  - mkdir -p /usr/share/keyrings
  - curl -L https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/$OS/Release.key | gpg --dearmor -o /usr/share/keyrings/libcontainers-archive-keyring.gpg (| apt-key add -)
  - curl -L https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable:/cri-o:/$VERSION/$OS/Release.key | gpg --dearmor -o /usr/share/keyrings/libcontainers-crio-archive-keyring.gpg (| apt-key add -)
  - apt-get update
  - apt-get install cri-o cri-o-runc
  - wget https://github.com/kubernetes-sigs/cri-tools/releases/download/$VERSION/crictl-$VERSION-linux-amd64.tar.gz
  - tar zxvf crictl-$VERSION-linux-amd64.tar.gz -C /usr/local/bin
  - rm -f crictl-$VERSION-linux-amd64.tar.gz 

- core binaries (kubeadm,kubelet,kubectl)
    - apt install -y apt-transport-https ca-certificates curl
    - mkdir -m 755 /etc/apt/keyrings
    - curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.27/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
    - echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.27/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
    - apt update
    - apt install -y kubeadm kubectl kubelet
    - apt-mark hold kubelet kubeadm kubectl
- *cgroup driver (systemd)
- master - init
    - kubeadm init --pod-network-cidr=<specific_to_certain_network_plugin_cidr> --cri-socket=unix:///var/run/crio/crio.sock *--apiserver-cert-extra-sans=<> *--apiserver-advertise-address=<ip_or_default_to_nodes_ip>  --control-plane-endpoint=<ha_ip_or_domainname>
    - mkdir -p $HOME/.kube
    - cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
    - chown $(id -u):$(id -g) $HOME/.kube/config
- network plugin (calico)
    - kubectl apply -f https://docs.projectcalico.org/v2.6/getting-started/kubernetes/installation/hosted/kubeadm/1.6/calico.yaml
- *storage plugin (storage class)
- node - join (add workers with --control-plane or masters)
- ingress controller


Update:

Backup. Velero/etcdctl snapshot  
# Master   
- kubeadm config migrate --old-config /etc/kubernetes/kubeadm-config.yaml --new-config /etc/kubernetes/kubeadm-config-new.yaml
    - update kubeadm
    - kubeadm upgrade plan
        - kubeadm upgrade apply [k8s-version]
        - kubeadm upgrade node (add. masters)
    - *upgrade network plugin
    - *upgrade storage plugin
    - kubectl drain node (--ignore-daemonsets)
    - update kubelet, kubectl
    - kubectl uncordon
# Worker
    - update kubeadm
    - kubeadm upgrade node
    - kubectl drain node (--ignore-daemonsets)
    - update kubelet, kubectl
    - kubectl uncordon 

kubectl get nodes


----
kubeadm init phases:

- preflight: Sanity checks on the node
- certs: Create all the required client and server certificates for the kube - scheduler, kubeproxy, etcd, and apiserver
- kubeconfig: Generate configuration files necessary for the cluster
- kubelet-start: Write and start the kubelet configuration
- control-plane: Generate the static pod manifests files that will start the apiserver, controller-manager and scheduler
- etcd: Start the etcd server
- upload-config: Store the kubeadm and kubelet configuration as a ConfigMap
- upload-certs: Store the generated certificates
- mark-control-plane: Signify whether a node is a part of the control plane
- bootstrap-token: Generate the token that is consumed by additional worker nodes to join the cluster
- kubelet-finalize: Update the kubelet when TLS bootstrap between new nodes is done
- addon: Install coredns and kube-proxy