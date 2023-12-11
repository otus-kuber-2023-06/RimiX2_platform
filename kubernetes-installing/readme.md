
## Установка 1.23

### Master
```
sudo setenforce 0
sudo sed -i ‘s/^SELINUX=enforcing$/SELINUX=permissive/’ /etc/selinux/config

sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
sudo swapoff -a

cat <<EOF | sudo tee /etc/modules-load.d/containerd.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter

??? net.ipv4.ip_forward = 1

sudo tee /etc/sysctl.d/kubernetes.conf<<EOF
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
net/bridge/bridge-nf-call-arptables = 1
EOF
sudo sysctl --system

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update -y
sudo apt install -y containerd.io
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd

sudo apt-get update && sudo apt-get install -y apt-transport-https curl
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo echo "deb https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt update -y
sudo apt -y install vim git curl wget kubelet=1.23.0-00 kubeadm=1.23.0-00 kubectl=1.23.0-00
sudo apt-mark hold kubelet kubeadm kubectl

sudo kubeadm config images pull --cri-socket /run/containerd/containerd.sock --kubernetes-version v1.23.0

sudo kubeadm init   --pod-network-cidr=10.244.0.0/16   --upload-certs --kubernetes-version=v1.23.0 --ignore-preflight-errors=Mem  --cri-socket /run/containerd/containerd.sock
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/v0.17.0/Documentation/kube-flannel.yml
```
### Workers

sudo kubeadm join 192.168.0.5:6443 --token 407c28.kzqtakqmxc4ri40l \
        --discovery-token-ca-cert-hash sha256:313449f617fa1de378564ef80e0161d65ab707ff126a406f29f0aff5adbc85d5


## Обновление до 1.24

sudo update
sudo apt-cache madison kubeadm - показать какие версии в каких репозиториях есть

sudo apt-mark unhold kubeadm
sudo apt-get install -y kubeadm=1.24.17-00
sudo apt-mark hold kubeadm
sudo kubeadm upgrade plan

sudo kubeadm upgrade apply v1.24.17

## (*) Установка кластера с 3 master-нодами и 2 worker-нодами с помощью kubeadm

Setup:
- 5 (3 master + 2 worker) VM/Bare metal (2xCPU, 4xRAM, 30GB) with unique machine IDs
- netwokr connectivity
- OS (debian 12)
    - apt update
- hostname
- ssh keys
- swap off
    - swapoff -a
    - vi /etc/fstab
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
    - kubeadm init --pod-network-cidr=192.168.0.0/16 --cri-socket=unix:///var/run/crio/crio.sock
    - mkdir -p $HOME/.kube
    - cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
    - chown $(id -u):$(id -g) $HOME/.kube/config
- network plugin (calico)
    - kubectl apply -f https://docs.projectcalico.org/v2.6/getting-started/kubernetes/installation/hosted/kubeadm/1.6/calico.yaml
- *storage plugin (storage class)
- node - join (add workers with --control-plane or masters)
- ingress controller


Update:
- master:
    - update kubeadm
    - kubeadm upgrade plan
        - kubeadm upgrade apply [k8s-version]
        - kubeadm upgrade node (add. masters)
    - *upgrade network plugin
    - *upgrade storage plugin
    - kubectl drain (--ignore-daemonsets)
    - update kubelet, kubectl
    - kubectl uncordon
- worker:
    - update kubeadm
    - kubeadm upgrade node
    - kubectl drain (--ignore-daemonsets)
    - update kubelet, kubectl
    - kubectl uncordon 
- kubectl get nodes




----
kubeadm init



* — apiserver-advertise-address string : The IP address the API Server will advertise it’s listening on. If not set the default network interface will be used.
* — pod-network-cidr string : Specify range of IP addresses for the pod network. If set, the control plane will automatically allocate CIDRs for every node.
* — apiserver-cert-extra-sans : Optional extra Subject Alternative Names (SANs) to use for the API Server serving certificate. Can be both IP addresses and DNS names.

The highly customizable kubeadm init command consists of these phases according to the official documentation:

preflight: Sanity checks on the node
certs: Create all the required client and server certificates for the kube scheduler, kubeproxy, etcd, and apiserver
kubeconfig: Generate configuration files necessary for the cluster
kubelet-start: Write and start the kubelet configuration
control-plane: Generate the static pod manifests files that will start the apiserver, controller-manager and scheduler
etcd: Start the etcd server
upload-config: Store the kubeadm and kubelet configuration as a ConfigMap
upload-certs: Store the generated certificates
mark-control-plane: Signify whether a node is a part of the control plane
bootstrap-token: Generate the token that is consumed by additional worker nodes to join the cluster
kubelet-finalize: Update the kubelet when TLS bootstrap between new nodes is done
addon: Install coredns and kube-proxy