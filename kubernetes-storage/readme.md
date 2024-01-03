# 12 (СSI плагины)

## Установка HostPath CSI драйвера

Клонирование репозитория с драйвером и запуск скрипта установки:
```
git clone https://github.com/kubernetes-csi/csi-driver-host-path
deploy/kubernetes-1.26/deploy.sh
```
Установка класса для динамического выделения диска:
```
kubectl apply -f ./hw/0-storage-sc.yml
kubectl get sc
NAME                           PROVISIONER                     RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE 
csi-hostpath-sc                hostpath.csi.k8s.io             Delete          Immediate              true                   59m 
```

Создание пода с динамическим диском класса "HostPath CSI":
```
kubectl apply -f ./hw/1-storage-pvc.yml
kubectl apply -f ./hw/2-storage-pod.yml
```

```
kubectl get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                 STORAGECLASS      REASON   AGE
pvc-0d01102f-ea8a-473f-b7d4-ead143e8f3d6   1Gi        RWO            Delete           Bound    default/storage-pvc   csi-hostpath-sc            2m14s

kubectl get pvc
NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
storage-pvc   Bound    pvc-0d01102f-ea8a-473f-b7d4-ead143e8f3d6   1Gi        RWO            csi-hostpath-sc   2m45s

kubectl get volumeattachments
NAME                                                                   ATTACHER              PV                                         NODE                        ATTACHED   AGE
csi-26ceb6d3354506dd957a1d1a3743e8b41ffa985ca9d230b80cc71f8f1bb36156   hostpath.csi.k8s.io   pvc-0d01102f-ea8a-473f-b7d4-ead143e8f3d6   cl1h66s7p14gbdtbldu8-amig   true       4m2s
```

Запишем что-нибудь на предоставленный диск:
```
kubectl exec -it storage-pod -- sh

echo "something" > /data/test.file
```

## Проверка работы снапшотов томов

`VolumeSnapshot` - заявка на создание снапшота
`VolumeSnapshotContent` - созданный по заявке снапшот определенного тома (может создаваться вручную администратором)
`VolumeSnapshotClass` - класс создания динамических снапошотов
`snapshot controller` - следит за соответствием между VolumeSnapshot и VolumeSnapshotContent

### Проверка наличия CRD для функционала снапшотов:
```
kubectl get volumesnapshotclasses.snapshot.storage.k8s.io 
kubectl get volumesnapshots.snapshot.storage.k8s.io 
kubectl get volumesnapshotcontents.snapshot.storage.k8s.io
```
```
kubectl apply -f https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/${SNAPSHOTTER_VERSION}/deploy/kubernetes/snapshot-controller/rbac-snapshot-controller.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/${SNAPSHOTTER_VERSION}/deploy/kubernetes/snapshot-controller/setup-snapshot-controller.yaml
```

Создим заявку на динамический снапшот:
```
kubectl apply -f ./hw/3-storage-vs.yml
```

Как видим, заявка обработана и снапшот создан:
```
kubectl get volumesnapshots
NAME            READYTOUSE   SOURCEPVC     SOURCESNAPSHOTCONTENT   RESTORESIZE   SNAPSHOTCLASS            SNAPSHOTCONTENT                                    CREATIONTIME   AGE
snapshot-demo   true         storage-pvc                           1Gi           csi-hostpath-snapclass   snapcontent-ef3c728e-a6a2-4b86-9ed5-f0060d5e1c56   14s            14s

kubectl get volumesnapshotcontents
NAME                                               READYTOUSE   RESTORESIZE   DELETIONPOLICY   DRIVER                VOLUMESNAPSHOTCLASS      VOLUMESNAPSHOT   VOLUMESNAPSHOTNAMESPACE   AGE
snapcontent-ef3c728e-a6a2-4b86-9ed5-f0060d5e1c56   true         1073741824    Delete           hostpath.csi.k8s.io   csi-hostpath-snapclass   snapshot-demo    default                   66s
```

Создадим новый под "new-pod" с новым диском большего размера из созданного ранее снапшота "snapshot-demo":
```
kubectl apply -f ./hw/4-new-pvc-from-vs.yml
kubectl apply -f ./hw/5-new-pod.yml
```

Проверим, что диск содержит файл из снапшота:
```
kubectl exec -it new-pod -- sh

cat /data/test.file
something
```
