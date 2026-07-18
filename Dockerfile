FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --no-save netlify-cli@latest

COPY . .

EXPOSE 8888

CMD ["./node_modules/.bin/netlify", "dev", "--host", "0.0.0.0", "--port", "8888"]
