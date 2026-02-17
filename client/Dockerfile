# syntax=docker/dockerfile:1.7
FROM node:20-alpine

WORKDIR /app

COPY package*.json /app/
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY . /app

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
