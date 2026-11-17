#!/usr/bin/env bash
set -euo pipefail
hrms_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
hrms_workers="${1:-4}"
case "$hrms_workers:${2:-}" in
  4:) hrms_compose="$hrms_root/deployments/compose.capacity.yaml" ;;
  4:shared) hrms_compose="$hrms_root/deployments/compose.shared.yaml" ;;
  1:) hrms_compose="$hrms_root/deployments/compose.yaml" ;;
  *) echo 'Choose 1, 4, or 4 shared.' >&2; exit 1 ;;
esac
if ! command -v docker >/dev/null 2>&1; then
  echo 'Install and start Docker with Compose v2, then try again.' >&2
  exit 1
fi
docker compose -f "$hrms_compose" --profile tools run --rm --no-deps init-secrets
docker compose -f "$hrms_compose" up --build -d --wait --wait-timeout 180
printf '%s\n' "HRMS is ready: http://localhost:${HRMS_HTTP_PORT:-8001}/login" 'Username: hradmin' \
  "Password file: $hrms_root/.runtime/docker-hrms-secrets/admin_password"
