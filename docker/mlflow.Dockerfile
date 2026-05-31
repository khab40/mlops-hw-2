FROM python:3.11-slim

RUN pip install --no-cache-dir \
        mlflow==3.12.0 \
        psycopg2-binary==2.9.10 \
        boto3==1.35.54

EXPOSE 5000
