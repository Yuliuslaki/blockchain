FROM python:3.10-slim

WORKDIR /app

COPY node.py /app/node.py
COPY packages/ /app/packages/
RUN pip install --no-index --find-links=/app/packages rsa

# Gunakan format exec untuk ENTRYPOINT agar argumen dari docker-compose terbaca dengan benar
ENTRYPOINT ["python", "node.py"]