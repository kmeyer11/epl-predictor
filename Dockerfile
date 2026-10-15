FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY epl_predictor ./epl_predictor
COPY site ./site
COPY scripts ./scripts

# The SQLite database and the website's data.js live outside the app dir so
# they survive rebuilds — mount a volume at /data. The link lets the page
# show the last export straight after a restart, before the refresh is done.
RUN ln -s /data/data.js site/data.js
ENV EPL_DATA_DIR=/data
ENV SITE_DIR=/data
ENV PYTHONUNBUFFERED=1
VOLUME /data

EXPOSE 8010
CMD ["sh", "scripts/serve.sh"]
