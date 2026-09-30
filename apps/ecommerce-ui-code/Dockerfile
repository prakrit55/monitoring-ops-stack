# Stage 1: Build the React client frontend
FROM node:20-alpine AS client-builder

WORKDIR /app/client

COPY client/package*.json ./
RUN npm install --legacy-peer-deps

COPY client/ ./
RUN npm run build

# Stage 2: Set up the Express backend gateway server
FROM node:20-alpine

WORKDIR /app/server

COPY server/package*.json ./
RUN npm install --only=production

COPY server/ ./
COPY --from=client-builder /app/client/build /app/client/build

EXPOSE 4000

CMD ["node", "server.js"]

