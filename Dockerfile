FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app/ ./backend/app/
COPY data/processed/fin/places.csv ./data/processed/fin/places.csv
COPY data/processed/fin/place_opening_hours.csv ./data/processed/fin/place_opening_hours.csv
COPY data/processed/merchants.csv ./data/processed/merchants.csv
COPY data/raw/dongbaekjeon/2026_부산의맛_식당목록.csv ./data/raw/dongbaekjeon/2026_부산의맛_식당목록.csv
COPY --from=frontend /build/frontend/dist/ ./frontend/dist/
WORKDIR /app/backend
EXPOSE 10000
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
