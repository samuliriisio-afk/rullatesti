FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATA_DIR=/data PORT=8000
VOLUME /data
EXPOSE 8000
# Yksi prosessi, useita säikeitä: työn tila pidetään levyllä, mutta lukitukset ovat prosessin muistissa.
CMD ["gunicorn","-w","1","--threads","8","--timeout","300","-b","0.0.0.0:8000","app:app"]
