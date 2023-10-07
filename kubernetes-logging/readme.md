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

kubectl create ns observability

helm show values elastic/elastic > EFK/es-values.yml
helm upgrade --install elasticsearch elastic/elasticsearch --namespace observability --values EFK/es-values.yml
kubectl get secret elasticsearch-master-credentials -o=jsonpath='{.data.password}' -n observability | base64 --decode
helm show values elastic/kibana > EFK/kibana-values.yml
helm upgrade --install kibana elastic/kibana --namespace observability --values EFK/kibana-values.yml
helm show values fluent/fluent-bit > EFK/f-bit-values.yml
helm upgrade --install fluent-bit fluent/fluent-bit --namespace observability --values EFK/f-bit-values.yml

## Ingress Controller

kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
## Grafana Loki
