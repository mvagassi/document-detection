# Gunakan base image Python versi 3.11
FROM python:3.11-alpine

# Tentukan direktori kerja di dalam container
WORKDIR /app

# Salin file requirements.txt ke dalam container
COPY . .
RUN mkdir -p /app/static \
    && apk add --no-cache git \
    && git describe --tags > VERSION \
    && apk del git \
    && apk update \
    && apk add --virtual build-deps gcc python3-dev musl-dev \
    && apk add --no-cache mariadb-dev \ 
    && apk add --no-cache supervisor \
    && pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt \
    && rm -f /app/core/config.py \
    && chmod -R 777 /app/static

# Expose port FastAPI (default port 8000)
EXPOSE 8000

#COPY supervisord.conf /etc/supervisord.conf
# Jalankan aplikasi FastAPI menggunakan uvicorn
CMD ["supervisord", "-c", "/etc/supervisord.conf"]