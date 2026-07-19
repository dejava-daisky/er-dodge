FROM node:22-alpine

WORKDIR /app

RUN apk add --no-cache python3

COPY . .

EXPOSE 8888

ENV HOST=0.0.0.0
ENV PORT=8888
ENV PYTHON_BIN=python3

CMD ["node", "server.mjs"]
