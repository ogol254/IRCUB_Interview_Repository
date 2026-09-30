FROM node:22-alpine AS build
WORKDIR /app
COPY section_01_technical/frontend/package*.json ./
RUN npm ci
COPY section_01_technical/frontend ./
RUN npm run build
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
