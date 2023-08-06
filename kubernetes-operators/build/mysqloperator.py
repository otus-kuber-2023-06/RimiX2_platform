import kopf
import yaml
import kubernetes
import time
import logging
from jinja2 import Environment, FileSystemLoader


def render_template(filename, vars_dict):
    env = Environment(loader=FileSystemLoader("./templates"))
    template = env.get_template(filename)
    yaml_manifest = template.render(vars_dict)
    json_manifest = yaml.load(yaml_manifest, Loader=yaml.Loader)
    return json_manifest


@kopf.on.delete("persistence.volume.claim")
def notify(body, spec, **kwargs):
    logging.info(f"Deleting {body['metadata']['name']}")


@kopf.on.create("otus.homework", "v1", "mysqls")
# Функция, которая будет запускаться при создании объектов тип MySQL:
def mysql_on_create(body, spec, **kwargs):
    # cохраняем в переменные содержимое описания MySQL из CR
    name = body["metadata"]["name"]
    image = body["spec"]["image"]
    password = body["spec"]["password"]
    database = body["spec"]["database"]
    storage_size = body["spec"]["storage_size"]
    namespace = body["metadata"]["namespace"]

    # Генерируем JSON манифесты для деплоя
    persistent_volume = render_template(
        "mysql-pv.yml.j2", {"name": name, "storage_size": storage_size}
    )
    persistent_volume_claim = render_template(
        "mysql-pvc.yml.j2", {"name": name, "storage_size": storage_size}
    )
    service = render_template("mysql-service.yml.j2", {"name": name})
    deployment = render_template(
        "mysql-deployment.yml.j2",
        {"name": name, "image": image, "password": password, "database": database},
    )

    # kopf.adopt(persistent_volume)
    # kopf.adopt(persistent_volume_claim)
    # kopf.adopt(service)
    # kopf.adopt(deployment)

    kopf.append_owner_reference(persistent_volume, owner=body)
    kopf.append_owner_reference(persistent_volume_claim, owner=body)
    kopf.append_owner_reference(service, owner=body)
    kopf.append_owner_reference(deployment, owner=body)

    api = kubernetes.client.CoreV1Api()

    pv_list = api.list_persistent_volume()
    if f"{name}-pv" in pv_list:
        api.delete_persistent_volume(f"{name}-pv")
        # Создаем mysql PV:
        api.create_persistent_volume(persistent_volume)

    # try:
    # Создаем mysql PV:
    #     print(api.create_persistent_volume(persistent_volume))
    # except kubernetes.client.exceptions.ApiException as e:
    #     if e.status == 409:
    #         pass
    #     else:
    #         raise e

    # Создаем mysql PVC:
    api.create_namespaced_persistent_volume_claim(namespace, persistent_volume_claim)
    # Создаем mysql SVC:
    api.create_namespaced_service(namespace, service)
    # Создаем mysql Deployment:
    api = kubernetes.client.AppsV1Api()
    api.create_namespaced_deployment(namespace, deployment)


@kopf.on.delete("otus.homework", "v1", "mysqls")
def delete_object_make_backup(body, **kwargs):
    return {"message": "mysql and its children resources deleted"}
