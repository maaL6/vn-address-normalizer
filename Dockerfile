FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir "transformers>=4.40,<5" rapidfuzz fastapi "uvicorn[standard]" "numpy<2"
COPY src/ src/
COPY data/gazetteer.json data/gazetteer.json
COPY web/ web/
COPY models/ models/
ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "vnaddr.api:app", "--host", "0.0.0.0", "--port", "8000"]
