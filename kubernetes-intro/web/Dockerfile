FROM nginx
RUN mkdir /app
RUN usermod -u 1001 nginx && groupmod -g 1001 nginx
ADD nginx.conf /etc/nginx/nginx.conf
COPY index.html /app
EXPOSE 8000
ENTRYPOINT [ "" ]
CMD  ["nginx"]