# WhatsApp bot backend — build from the REPO ROOT:
#   docker build -f whatsapp/Dockerfile .
# (the server needs app.py, st_stub.py, sarvam.py and the index files)
FROM python:3.12-slim

WORKDIR /srv
COPY whatsapp/requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY st_stub.py app.py sarvam.py embeddings.py constituencies_list.json ./
COPY embed_chunks.pkl embed_index_part0.npz embed_index_part1.npz ./
COPY corpus_files/District_Data ./corpus_files/District_Data
COPY whatsapp/server.py ./whatsapp/server.py

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn whatsapp.server:app --host 0.0.0.0 --port ${PORT}"]
