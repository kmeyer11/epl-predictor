FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY epl_predictor ./epl_predictor
COPY site ./site
COPY scripts ./scripts

# The SQLite database lives outside the app dir so it survives image
# rebuilds — mount a volume at /data. site/data.js is rebuilt on every start.
ENV EPL_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1
VOLUME /data

EXPOSE 8010
CMD ["sh", "scripts/serve.sh"]
