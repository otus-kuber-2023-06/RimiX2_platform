FROM nginx
#LABEL org.opencontainers.image.source="https://github.com/otus-kuber-2023-06/RimiX2_platform"
RUN mkdir /app
RUN usermod -u 1001 nginx && groupmod -g 1001 nginx
ADD nginx.conf /etc/nginx/nginx.conf
# COPY index.html /app
EXPOSE 8000
ENTRYPOINT [ "" ]
CMD  ["nginx"]