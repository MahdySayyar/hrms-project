#!/bin/sh
set -eu
umask 077
hrms_redis_password="$(cat /run/secrets/redis_password)"
test "${#hrms_redis_password}" -ge 12
# Only the generated token alphabet is valid; prevent config-line injection.
case "$hrms_redis_password" in *[!A-Za-z0-9_-]*) exit 1 ;; esac
printf 'bind 0.0.0.0\nprotected-mode yes\nsave ""\nappendonly no\nmaxmemory 256mb\nmaxmemory-policy noeviction\nrequirepass %s\n' "$hrms_redis_password" > /tmp/hrms-redis.conf
unset hrms_redis_password
exec redis-server /tmp/hrms-redis.conf
