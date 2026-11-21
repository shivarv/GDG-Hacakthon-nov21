# Cloud Run variant of frontend/Dockerfile: same build, but nginx listens on $PORT
# and proxies /api to the helpdesk-backend Cloud Run URL ($BACKEND_URL).
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
RUN rm -f /etc/nginx/conf.d/default.conf
COPY cloudrun.nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV PORT=8080 \
    NGINX_ENVSUBST_FILTER="^(PORT|BACKEND_URL)$"
EXPOSE 8080
