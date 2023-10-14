#9 

## Infra

kubectl taint nodes node[1-3] node-role=infra:NoSchedule
kubectl label nodes -l [1-3] role=infra
kubectl label nodes -l [4] role=workload

## Demo microservices

k create ns demo
wget https://raw.githubusercontent.com/express42/otus-platform-snippets/master/Module-02/Logging/microservices-demo-without-resources.yaml


## Elastic Stack (fluent bit)

helm repo add elastic https://helm.elastic.co
helm repo add fluent https://fluent.github.io/helm-charts

kubectl create ns observe

helm show values elastic/elastic > EFK/es-values.yml
helm upgrade --install elasticsearch elastic/elasticsearch --namespace observe --values elasticsearch.values.yaml
kubectl get secret elasticsearch-master-credentials -o=jsonpath='{.data.password}' -n observe | base64 --decode
helm show values elastic/kibana > EFK/kibana-values.yml
helm upgrade --install kibana elastic/kibana --namespace observe --values kibana.values.yaml
helm show values fluent/fluent-bit > EFK/f-bit-values.yml
helm upgrade --install fluent-bit fluent/fluent-bit --namespace observe --values fluent-bit.values.yaml

## Ingress Controller

helm show values ingress-nginx --repo https://kubernetes.github.io/ingress-nginx > ingress-nginx.values.yaml

helm upgrade --install ingress-nginx ingress-nginx \
  --repo https://kubernetes.github.io/ingress-nginx \
  --namespace ingress-nginx --create-namespace --values ingress-nginx.values.yaml

## Prometheus Elasticsearch Exporter

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm show values prometheus-community/kube-prometheus-stack > prom-stack.values.yaml
helm upgrade --install prom-operator prometheus-community/kube-prometheus-stack --namespace observe --values prom-stack.values.yaml

helm show values prometheus-community/prometheus-elasticsearch-exporter > es-prom-exporter.values.yaml
helm upgrade --install es-prom-exporter prometheus-community/prometheus-elasticsearch-exporter --namespace observe --values es-prom-exporter.values.yaml

## (*) Duplicate field '@timestamp'


## Grafana Loki
