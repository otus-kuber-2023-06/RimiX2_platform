import kopf
import yaml
import kubernetes
import time
import logging as logger
from jinja2 import Environment, FileSystemLoader


def render_template(filename, vars_dict):
    env = Environment(loader=FileSystemLoader("./templates"))
    template = env.get_template(filename)
    yaml_manifest = template.render(vars_dict)
    json_manifest = yaml.load(yaml_manifest, Loader=yaml.Loader)
    return json_manifest


# @kopf.on.delete("pv")
# def notify_pv_delete(body, spec, **kwargs):
#     logger.info(f"Caught deleting PV {body['metadata']['name']} event")

# @kopf.on.update('ms')
# def resize_mysql_on_update(spec, metadata, **kwargs):
#     logger.info(f"Caught updating MS {metadata['name']} event")
#     new_size = spec.get('storage_size', None)
#     if not new_size:
#         raise kopf.PermanentError(f"Size must be set. Got {new_size!r}.")
    
#     namespace = metadata["namespace"]
#     name = metadata["name"]
#     pvc_patch = {'spec': {'resources': {'requests': {'storage': new_size}}}}

#     api_coreV1 = kubernetes.client.CoreV1Api()
#     obj = api_coreV1.patch_namespaced_persistent_volume_claim(
#         namespace= namespace,
#         name=name,
#         body=pvc_patch,
#     )


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
    restore_job = render_template('restore-job.yml.j2', {
        'name': name,
        'image': image,
        'password': password,
        'database': database})
    
    # kopf.adopt(persistent_volume)
    # kopf.adopt(persistent_volume_claim)
    # kopf.adopt(service)
    # kopf.adopt(deployment)

    # kopf.append_owner_reference(persistent_volume, owner=body)
    kopf.append_owner_reference(persistent_volume_claim, owner=body)
    kopf.append_owner_reference(service, owner=body)
    kopf.append_owner_reference(deployment, owner=body)
    kopf.append_owner_reference(restore_job, owner=body)

    api_coreV1 = kubernetes.client.CoreV1Api()

    # Проверка на наличие существующего PV и его удаление
    if any(
        pv.metadata.name == f"{name}-pv"
        for pv in api_coreV1.list_persistent_volume().items
    ):
        logger.info(f"PV {name}-pv already exists. Deleting it ...")
        api_coreV1.delete_persistent_volume(f"{name}-pv")

    # pv_list_1 = api.list_persistent_volume(field_selector = f'metadata.name={name}-pv')
    # if len(pv_list_1.items)==1 :
    #     logger.info(f"PV {name}-pv already exists. Deleting ...")
    #     api.delete_persistent_volume(f"{name}-pv")

    # # Создаем mysql PV:
    # api_coreV1.create_persistent_volume(persistent_volume)

    try:
    #Создаем mysql PV:
        api_coreV1.create_persistent_volume(persistent_volume)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warning(f"PV {name}-p is not deleted yet")
            raise e

    # Создаем mysql PVC:
    api_coreV1.create_namespaced_persistent_volume_claim(
        namespace, persistent_volume_claim
    )
    # Создаем mysql SVC:
    api_coreV1.create_namespaced_service(namespace, service)
    # Создаем mysql Deployment:
    api_appsV1 = kubernetes.client.AppsV1Api()
    api_appsV1.create_namespaced_deployment(namespace, deployment)

    # Пытаемся восстановиться из backup
    try:
        api_batchV1 = kubernetes.client.BatchV1Api()
        api_batchV1.create_namespaced_job(namespace, restore_job)
    except kubernetes.client.rest.ApiException:
        pass

    # Cоздаем PVC и PV для бэкапов:
    try:
        backup_pv = render_template("backup-pv.yml.j2", {"name": name})
        api_coreV1.create_persistent_volume(backup_pv)
    except kubernetes.client.exceptions.ApiException:
        pass
    try:
        backup_pvc = render_template("backup-pvc.yml.j2", {"name": name})
        api_coreV1.create_namespaced_persistent_volume_claim(namespace, backup_pvc)
    except kubernetes.client.exceptions.ApiException:
        pass


def delete_success_jobs(instance_name, namespace):
    logger.info("Deleting success jobs ...")
    api = kubernetes.client.BatchV1Api()
    jobs = api.list_namespaced_job(namespace)
    for job in jobs.items:
        jobname = job.metadata.name
        if (jobname == f"backup-{instance_name}-job") or (
            jobname == f"restore-{instance_name}-job"
        ):
            if job.status.succeeded == 1:
                api.delete_namespaced_job(
                    jobname, namespace, propagation_policy="Background"
                )

def wait_until_job_end(jobname, namespace):
    api_batchV1 = kubernetes.client.BatchV1Api()
    job_finished = False
    jobs = api_batchV1.list_namespaced_job(namespace)
    while (not job_finished) and \
            any(job.metadata.name == jobname for job in jobs.items):
        time.sleep(1)
        jobs = api_batchV1.list_namespaced_job(namespace)
        for job in jobs.items:
            if job.metadata.name == jobname:
                logger.info(f"Job {jobname} found, waiting for complete")
                if job.status.succeeded == 1:
                    logger.info(f"Job {jobname} completed")
                    job_finished = True

@kopf.on.delete("otus.homework", "v1", "mysqls")
def delete_object_make_backup(body, **kwargs):
    name = body["metadata"]["name"]
    image = body["spec"]["image"]
    password = body["spec"]["password"]
    database = body["spec"]["database"]
    namespace = body["metadata"]["namespace"]

    delete_success_jobs(name, namespace)

    # Cоздаем backup job:
    api_batchV1 = kubernetes.client.BatchV1Api()
    backup_job = render_template(
        "backup-job.yml.j2",
        {"name": name, "image": image, "password": password, "database": database},
    )
    api_batchV1.create_namespaced_job(namespace, backup_job)
    wait_until_job_end(f"backup-{name}-job", namespace)
    return {"message": "mysql and its children resources deleted"}
