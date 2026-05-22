# Build stage
FROM node:20-slim AS builder

WORKDIR /app

# Copy package descriptors
COPY package.json package-lock.json /app/
COPY packages/shade-engine/package.json /app/packages/shade-engine/
COPY packages/shared-types/package.json /app/packages/shared-types/
COPY apps/web/package.json /app/apps/web/

# Install Node dependencies
RUN npm ci

# Copy source files
COPY packages/shade-engine /app/packages/shade-engine
COPY packages/shared-types /app/packages/shared-types
COPY apps/web /app/apps/web

# Build the Web client and local dependency packages
RUN npm run build --workspaces --if-present

# Production serving stage
FROM nginx:alpine

# Copy built files to nginx
COPY --from=builder /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
