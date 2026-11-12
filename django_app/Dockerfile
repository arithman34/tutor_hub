# Stage 1: build the public pages' CSS and the React app.
# Node never reaches the final image; only the files in static/ it produces do.
FROM node:22-slim AS frontend

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci
COPY spa/package.json spa/package-lock.json ./spa/
RUN npm ci --prefix spa

COPY frontend ./frontend
COPY templates ./templates
RUN npm run build

# Vite builds into ../static/spa, i.e. /build/static/spa.
COPY spa ./spa
RUN npm run build --prefix spa

# Stage 2: the Django app.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/static/css/app.css static/css/app.css
COPY --from=frontend /build/static/spa static/spa

RUN python manage.py collectstatic --noinput

EXPOSE 8000

RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
