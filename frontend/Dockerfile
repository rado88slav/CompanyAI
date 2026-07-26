FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src

RUN npm run typecheck \
    && npm run build \
    && find dist -name '*.map' -type f -delete

FROM nginx:1.27-alpine AS runtime

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=10s \
    CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
