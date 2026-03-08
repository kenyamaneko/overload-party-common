FROM postgres:16-alpine

RUN apk add --no-cache curl \
 && curl -sL https://github.com/sqldef/sqldef/releases/latest/download/psqldef_linux_amd64.tar.gz | tar xz -C /usr/local/bin/

COPY schema_postgres.sql /migration/schema_postgres.sql
COPY grant_iam.sql /migration/grant_iam.sql
COPY entrypoint.sh /migration/entrypoint.sh
RUN chmod +x /migration/entrypoint.sh

ENTRYPOINT ["/migration/entrypoint.sh"]
