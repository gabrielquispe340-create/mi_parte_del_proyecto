FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build -- --configuration production

FROM nginx:1.27-alpine
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
# nginx genera default.conf desde la plantilla al arrancar, reemplazando ${PORT} y
# ${BACKEND_URL}. Los valores de abajo sirven para Docker Compose; Railway los sobrescribe.
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV PORT=80 BACKEND_URL=http://backend:8000
EXPOSE 80
