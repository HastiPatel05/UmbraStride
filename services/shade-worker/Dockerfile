# UmbraStride shade-worker — Express + building-aware shade profiling
FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
COPY packages/shared-types/package.json packages/shared-types/
COPY packages/shade-engine/package.json packages/shade-engine/
COPY services/shade-worker/package.json services/shade-worker/

RUN npm ci --workspace=@umbrastride/shade-worker --include-workspace-root

COPY packages/shared-types packages/shared-types
COPY packages/shade-engine packages/shade-engine
COPY services/shade-worker services/shade-worker

RUN npm run build -w @umbrastride/shade-worker

ENV SHADE_WORKER_PORT=3001
ENV NODE_ENV=production

EXPOSE 3001

CMD ["npm", "run", "start", "-w", "@umbrastride/shade-worker"]
