# UmbraStride web — Vite build + nginx
FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY packages/shared-types/package.json packages/shared-types/
COPY packages/shade-engine/package.json packages/shade-engine/

RUN npm ci --workspace=@umbrastride/web --include-workspace-root

COPY apps/web apps/web
COPY packages/shared-types packages/shared-types
COPY packages/shade-engine packages/shade-engine

ARG VITE_API_URL=/api
ARG VITE_DEFAULT_AOI=az-phoenix
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DEFAULT_AOI=$VITE_DEFAULT_AOI

RUN npm run build -w @umbrastride/web

FROM nginx:alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80
