FROM node:12

RUN mkdir -p /ctf/app
WORKDIR /ctf/app

COPY ./package.json ./
COPY ./package-lock.json ./
RUN npm install

COPY ./index.js ./
COPY ./index.html ./
EXPOSE 8000

CMD ["node", "index.js"]