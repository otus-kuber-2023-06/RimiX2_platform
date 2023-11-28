FROM python:3.9.18-slim-bookworm
COPY . .
RUN pip install -r requirements.txt
CMD kopf run mysql-operator.py