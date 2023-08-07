FROM python:3.9.2
COPY templates ./templates
COPY mysql-operator.py ./mysql-operator.py
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
CMD kopf run /mysql-operator.py