FROM node:20-slim
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY index.js ./
RUN mkdir -p /app/auth_session
ENV AUTH_DIR=/app/auth_session
ENV PORT=3100
EXPOSE 3100
VOLUME ["/app/auth_session"]
CMD ["node", "index.js"]
