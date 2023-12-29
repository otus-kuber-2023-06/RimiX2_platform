# 12 (kubernetes storage)

## Установка HostPath CSI драйвера

### Проверка наличия CRD для функционала снапшотов:
```
kubectl get volumesnapshotclasses.snapshot.storage.k8s.io 
kubectl get volumesnapshots.snapshot.storage.k8s.io 
kubectl get volumesnapshotcontents.snapshot.storage.k8s.io
```
Установка:
```
git clone https://github.com/kubernetes-csi/csi-driver-host-path
deploy/kubernetes-1.26/deploy.sh
```

```
for i in ./examples/csi-storageclass.yaml ./examples/csi-pvc.yaml ./examples/csi-app.yaml; do kubectl apply -f $i; done
```
```
kubectl get pv
kubectl get pvc
kubectl describe pods/my-csi-app
```
```
kubectl exec -it my-csi-app /bin/sh
touch /data/hello-world
```
```
kubectl exec -it $(kubectl get pods --selector app=csi-hostpathplugin -o jsonpath='{.items[*].metadata.name}') -c hostpath /bin/sh
find / -name hello-world
```
```
kubectl describe volumeattachment
```