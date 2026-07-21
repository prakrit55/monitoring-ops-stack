FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json tsconfig.json ./
RUN npm ci
COPY index.ts ./
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY --from=builder /app/dist ./dist
COPY proto /app/proto
ENV PORT=8082
ENV PROTO_PATH=/app/proto/service.proto
EXPOSE 8082
CMD ["node", "dist/index.js"]
