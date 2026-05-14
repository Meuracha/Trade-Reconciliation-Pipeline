FROM apache/airflow:2.9.1-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

RUN pip install --no-cache-dir psycopg2-binary==2.9.9

COPY requirements.txt .
RUN pip install --no-cache-dir --no-deps dbt-postgres==1.8.0 \
    && pip install --no-cache-dir -r requirements.txt