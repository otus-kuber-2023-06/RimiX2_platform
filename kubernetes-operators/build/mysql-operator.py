import kopf
import json
import yaml
import kubernetes
from kubernetes.stream import stream
import time
import logging as logger
from jinja2 import Environment, FileSystemLoader
import base64


def render_template(filename, vars_dict):
    env = Environment(loader=FileSystemLoader("./templates"))
    # env.filters['b64encode'] = base64.b64encode
    template = env.get_template(filename)
    yaml_manifest = template.render(vars_dict)
    json_manifest = yaml.load(yaml_manifest, Loader=yaml.Loader)
    return json_manifest


# Функция обновления поля в status subresource
def update_status(body, msg):
    custom_api = kubernetes.client.CustomObjectsApi()
    update_payload = {"status": {"message": msg}}
    custom_api.patch_namespaced_custom_object_status(
        group="otus.homework",
        version="v1",
        namespace=body["metadata"]["namespace"],
        plural="mysqls",
        name=body["metadata"]["name"],
        body=update_payload,
    )


@kopf.on.create("otus.homework", "v1", "mysqls")
# Функция, которая будет запускаться при создании объектов тип MySQL:
def create(body, spec, **kwargs):
    # cохраняем в переменные содержимое описания MySQL из CR
    name = body["metadata"]["name"]
    image = spec["image"]
    root_password = body["spec"]["password"]
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

    secret = render_template(
        "mysql-secret.yml.j2",
        {"name": name, "encoded_password": base64.b64encode(root_password.encode("utf-8")).decode("utf-8")},
    )
    deployment = render_template(
        "mysql-deployment.yml.j2",
        {"name": name, "image": image, "password": root_password, "database": database},
    )
    restore_job = render_template(
        "restore-job.yml.j2",
        {"name": name, "image": image, "database": database},
    )

    # kopf.adopt(persistent_volume)
    # kopf.adopt(persistent_volume_claim)
    # kopf.adopt(service)
    # kopf.adopt(deployment)

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

    try:
        # Создаем mysql PV:
        api_coreV1.create_persistent_volume(persistent_volume)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warning(f"PV {name}-p is not deleted yet")
            raise e

    # Создаем mysql PVC:
    api_coreV1.create_namespaced_persistent_volume_claim(namespace, persistent_volume_claim)
    # Создаем mysql SVC:
    api_coreV1.create_namespaced_service(namespace, service)

    try:
        # Создаём mysql Secret (с паролем для root), если не его не существует:
        api_coreV1.create_namespaced_secret(namespace, secret)
    except kubernetes.client.exceptions.ApiException:
        pass

    # Создаем mysql Deployment:
    api_appsV1 = kubernetes.client.AppsV1Api()
    deploy = api_appsV1.create_namespaced_deployment(namespace, deployment)

    # Если есть бэкап,
    if any(
        pv.metadata.name == f"backup-{name}-pv"
        for pv in api_coreV1.list_persistent_volume().items
    ) and any(
        pvc.metadata.name == f"backup-{name}-pvc"
        for pvc in api_coreV1.list_namespaced_persistent_volume_claim(namespace).items
    ):
        logger.info("Backup exists")
        # пытаемся восстановиться из backup
        try:
            api_batchV1 = kubernetes.client.BatchV1Api()
            job = api_batchV1.create_namespaced_job(namespace, restore_job)
            logger.info(f"The {name} is trying to restore DB data from backup")
            if wait_until_job_end(job.metadata.name, namespace):
                update_status(body, "Restoring DB have succeed")
            else:
                update_status(body, "Restoring DB have failed")
        except kubernetes.client.rest.ApiException:
            update_status(body, "Restoring DB have failed")
    else:
        update_status(body, "DB backup not found")

    # Cоздаем PVC и PV для будущего бэкапа (если они есть, пропускаем их создание):
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
    logger.info(f"MySQL instance created")
    return {"deployment-name": deploy.metadata.name}


def delete_success_jobs(instance_name, namespace):
    logger.info("Deleting success jobs ...")
    api = kubernetes.client.BatchV1Api()
    jobs = api.list_namespaced_job(namespace)
    for job in jobs.items:
        jobname = job.metadata.name
        print(jobname)
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
    job_succeed = False
    jobs = api_batchV1.list_namespaced_job(namespace)
    while (not job_finished) and any(
        job.metadata.name == jobname for job in jobs.items
    ):
        time.sleep(1)
        jobs = api_batchV1.list_namespaced_job(namespace)
        for job in jobs.items:
            if job.metadata.name == jobname:
                logger.info(f"Job {jobname} found, waiting for complete")
                if job.status.succeeded == 1:
                    logger.info(f"Job {jobname} completed")
                    job_finished = True
                    job_succeed = True
    return job_succeed


@kopf.on.delete("otus.homework", "v1", "mysqls")
def delete_object_make_backup(body, **kwargs):
    name = body["metadata"]["name"]
    image = body["spec"]["image"]
    database = body["spec"]["database"]
    namespace = body["metadata"]["namespace"]
    
    # Cоздаем backup job:
    api_batchV1 = kubernetes.client.BatchV1Api()
    backup_job = render_template(
        "backup-job.yml.j2",
        {"name": name, "image": image, "database": database},
    )
    api_batchV1.create_namespaced_job(namespace, backup_job)
    wait_until_job_end(f"backup-{name}-job", namespace)

    delete_success_jobs(name, namespace)


# Меняем пароль суперпользователя на сервере
@kopf.on.field("otus.homework", "v1", "mysqls", field="spec.password")
def change_rootpswd(old, new, status, namespace, body, **kwargs):
    if old is None:
        return

    logger.info("Changing root-password ...")

    api_coreV1 = kubernetes.client.CoreV1Api()
    secret_name = body["metadata"]["name"]
    current_secret = api_coreV1.read_namespaced_secret(secret_name, namespace)
    real_old = base64.b64decode((current_secret.data['root-password']).encode("utf-8")).decode("utf-8")

    dpl_name = status["create"]["deployment-name"]
    api_appsV1 = kubernetes.client.AppsV1Api()
    dpl = api_appsV1.read_namespaced_deployment(dpl_name, namespace)
    # print(deployment)

    json_line = json.dumps(dpl.spec.selector.match_labels)
    data = json.loads(json_line)
    for key, value in data.items():
        selector_str = "{0}={1}".format(key, value)

    pods = api_coreV1.list_namespaced_pod(
        namespace, watch=False, label_selector=selector_str
    )

    for pod in pods.items:
        pod_name = pod.metadata.name

    while True:
        resp = api_coreV1.read_namespaced_pod(pod_name, namespace)
        if resp.status.phase == "Running":
            break
        else:
            logger.info("Instance pod is not running")
        time.sleep(5)

    db_name = body["spec"]["database"]
    exec_command = [
        "mysql",
        f"-p{real_old}",
        "-e",
        f"ALTER USER 'root'@'%' IDENTIFIED BY '{new}';ALTER USER 'root'@'localhost' IDENTIFIED BY '{new}'",
        db_name,
    ]
    resp = stream(
        api_coreV1.connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        command=exec_command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    logger.debug(f"Exec result: {resp}")

    new_data = {
        "root-password": base64.b64encode(new.encode("utf-8")).decode("utf-8")
    }
    current_secret.data.update(new_data)
    api_coreV1.replace_namespaced_secret(secret_name, namespace, body=current_secret)

    for pod in pods.items:
        api_coreV1.delete_namespaced_pod(pod.metadata.name, namespace, grace_period_seconds=0)

    # current_scale = api_appsV1.read_namespaced_deployment_scale(dpl_name, namespace)
    # current_scale.spec.replicas = 0
    # current_scale = api_appsV1.replace_namespaced_deployment_scale(dpl_name, namespace, body=current_scale)
    # current_scale.spec.replicas = 1
    # current_scale = api_appsV1.replace_namespaced_deployment_scale(dpl_name, namespace, body=current_scale) 

    logger.info(f"Root-password changed from {real_old} to {new}")

