FROM node:20-slim

WORKDIR /app

# Copy root package.json and workspace package.json files
COPY package.json package-lock.json /app/
COPY packages/shade-engine/package.json /app/packages/shade-engine/
COPY packages/shared-types/package.json /app/packages/shared-types/
COPY services/shade-worker/package.json /app/services/shade-worker/

# Install Node dependencies
RUN npm ci

# Copy source code
COPY packages/shade-engine /app/packages/shade-engine
COPY packages/shared-types /app/packages/shared-types
COPY services/shade-worker /app/services/shade-worker

# Build TypeScript
RUN npm run build --workspaces --if-present

EXPOSE 3001

CMD ["npm", "run", "start", "-w", "@umbrastride/shade-worker"]
