FROM pgvector/pgvector:pg16

COPY postgres-entrypoint.sh /usr/local/bin/postgres-entrypoint.sh
RUN chmod +x /usr/local/bin/postgres-entrypoint.sh

COPY init.sql /docker-entrypoint-initdb.d/init.sql

ENTRYPOINT ["/usr/local/bin/postgres-entrypoint.sh"]
