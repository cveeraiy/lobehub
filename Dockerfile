## Set global build ENV
ARG NODEJS_VERSION="24"

## Base image for all building stages
FROM node:${NODEJS_VERSION}-slim AS base

ARG USE_CN_MIRROR

ENV DEBIAN_FRONTEND="noninteractive"

RUN set -e && \
    if [ "${USE_CN_MIRROR:-false}" = "true" ]; then \
        sed -i "s/deb.debian.org/mirrors.ustc.edu.cn/g" "/etc/apt/sources.list.d/debian.sources"; \
    fi && \
    apt update && \
    apt install ca-certificates proxychains-ng -qy && \
    mkdir -p /distroless/bin /distroless/etc /distroless/etc/ssl/certs /distroless/lib && \
    cp /usr/lib/$(arch)-linux-gnu/libproxychains.so.4 /distroless/lib/libproxychains.so.4 && \
    cp /usr/lib/$(arch)-linux-gnu/libdl.so.2 /distroless/lib/libdl.so.2 && \
    cp /usr/bin/proxychains4 /distroless/bin/proxychains && \
    cp /etc/proxychains4.conf /distroless/etc/proxychains4.conf && \
    cp /usr/lib/$(arch)-linux-gnu/libstdc++.so.6 /distroless/lib/libstdc++.so.6 && \
    cp /usr/lib/$(arch)-linux-gnu/libgcc_s.so.1 /distroless/lib/libgcc_s.so.1 && \
    cp /usr/lib/$(arch)-linux-gnu/librt.so.1 /distroless/lib/librt.so.1 && \
    cp /usr/local/bin/node /distroless/bin/node && \
    cp /etc/ssl/certs/ca-certificates.crt /distroless/etc/ssl/certs/ca-certificates.crt && \
    rm -rf /tmp/* /var/lib/apt/lists/* /var/tmp/*

## Builder image, install all the dependencies and build the app
FROM base AS builder

ARG USE_CN_MIRROR
ARG FEATURE_FLAGS

ENV FEATURE_FLAGS="${FEATURE_FLAGS}"

ENV APP_URL="http://app.com" \
    DATABASE_DRIVER="node" \
    DATABASE_URL="postgres://postgres:password@localhost:5432/postgres" \
    KEY_VAULTS_SECRET="use-for-build" \
    AUTH_SECRET="use-for-build"

# Node
ENV NODE_OPTIONS="--max-old-space-size=8192"

WORKDIR /app

COPY package.json pnpm-workspace.yaml ./
COPY .npmrc ./
COPY packages ./packages
COPY patches ./patches

RUN set -e && \
    if [ "${USE_CN_MIRROR:-false}" = "true" ]; then \
        export SENTRYCLI_CDNURL="https://npmmirror.com/mirrors/sentry-cli"; \
        npm config set registry "https://registry.npmmirror.com/"; \
        echo 'canvas_binary_host_mirror=https://npmmirror.com/mirrors/canvas' >> .npmrc; \
    fi && \
    export COREPACK_NPM_REGISTRY=$(npm config get registry | sed 's/\/$//') && \
    npm i -g corepack@latest && \
    corepack enable && \
    corepack use $(sed -n 's/.*"packageManager": "\(.*\)".*/\1/p' package.json) && \
    pnpm i && \
    mkdir -p /deps && \
    cd /deps && \
    pnpm init && \
    pnpm add pg drizzle-orm

COPY . .

# Prebuild: env checks (checkDeprecatedAuth, checkRequiredEnvVars, printEnvInfo)
RUN pnpm exec tsx scripts/dockerPrebuild.mts

# run build standalone for docker version
RUN npm run build:docker

## Production frontend image: nginx serves the SPA and proxies backend paths to Python.
FROM nginx:1.27-alpine AS frontend

ENV PYTHON_BACKEND_URL="http://python-backend:8000"

COPY docker/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist/web /usr/share/nginx/html/web
COPY --from=builder /app/dist/mobile /usr/share/nginx/html/mobile

RUN set -e; \
    if [ -f /usr/share/nginx/html/mobile/index.mobile.html ]; then \
      cp /usr/share/nginx/html/mobile/index.mobile.html /usr/share/nginx/html/mobile/index.html; \
    fi

EXPOSE 3210/tcp
