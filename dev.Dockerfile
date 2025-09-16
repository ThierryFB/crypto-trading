FROM node:hydrogen

WORKDIR /app

COPY package.json .
# COPY index.js .
COPY .eslintrc .

RUN npm install --force

EXPOSE 3200

CMD ["npm", "run", "start"]