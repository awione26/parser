FROM mysql:8.4

COPY --chmod=0555 docker/mysql/grant-runtime-users.sh /usr/local/bin/grant-runtime-users

ENTRYPOINT ["/usr/local/bin/grant-runtime-users"]
