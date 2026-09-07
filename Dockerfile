FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web/package.json web/package-lock.json* web/
RUN npm --prefix web ci

COPY . .
RUN npm --prefix web run build

RUN chmod +x start.sh

ENV PORT=8080
ENV PYCLIPS_DATA_DIR=/data
RUN mkdir -p /data
EXPOSE 8080
CMD ["./start.sh"]
