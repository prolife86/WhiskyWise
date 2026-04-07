FROM node:20-alpine

RUN apk add --no-cache python3 make g++

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

RUN mkdir -p /data/uploads

ENV PORT=3000
ENV NODE_ENV=production

EXPOSE 3000

VOLUME ["/data"]

CMD ["node", "src/server.js"]
