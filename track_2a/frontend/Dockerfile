# Stage 1: build the static files with Vite
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Vite reads VITE_* variables at build time, so they are build arguments here
ARG VITE_API_URL=http://localhost:8000/api/v1
ARG VITE_USE_MOCK=true
ENV VITE_API_URL=$VITE_API_URL VITE_USE_MOCK=$VITE_USE_MOCK

COPY . .
RUN npm run build

# Stage 2: serve the files with nginx
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
