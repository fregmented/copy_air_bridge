#!/usr/bin/env bash
set -euo pipefail

SERVICE_PREFIX="copy-air-bridge"
TEMPLATE_NAME="${SERVICE_PREFIX}.service.template"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_PATH="${PROJECT_DIR}/deploy/systemd/${TEMPLATE_NAME}"
INSTALL_SYSTEM_UNIT=0
CUSTOM_VALUE=""

usage() {
  cat <<USAGE
Usage: $0 <custom_value> [--install]

Renders ${SERVICE_PREFIX}-<custom_value>.service using the current working
directory as the systemd WorkingDirectory, then runs uv sync.

Options:
  --install  Install to /etc/systemd/system, reload systemd, enable and restart.
USAGE
}

while (($#)); do
  case "$1" in
    --install)
      INSTALL_SYSTEM_UNIT=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "${CUSTOM_VALUE}" ]]; then
        echo "Only one custom_value is allowed." >&2
        usage >&2
        exit 2
      fi
      CUSTOM_VALUE="$1"
      ;;
  esac
  shift
done

if [[ -z "${CUSTOM_VALUE}" ]]; then
  echo "Missing required custom_value." >&2
  usage >&2
  exit 2
fi

if [[ ! "${CUSTOM_VALUE}" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
  echo "custom_value may contain only letters, numbers, dot, underscore, at sign, and dash." >&2
  exit 2
fi

SERVICE_NAME="${SERVICE_PREFIX}-${CUSTOM_VALUE}.service"
OUTPUT_PATH="${PROJECT_DIR}/deploy/systemd/${SERVICE_NAME}"

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Template not found: ${TEMPLATE_PATH}" >&2
  exit 1
fi

if [[ ! -f "${PWD}/pyproject.toml" ]]; then
  echo "Run this script from the repository root containing pyproject.toml." >&2
  exit 1
fi

UV_BIN="$(command -v uv)"
CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"
WORKING_DIRECTORY="$(pwd -P)"

uv sync --frozen

uv run python - "${TEMPLATE_PATH}" "${OUTPUT_PATH}" \
  "${CURRENT_USER}" "${CURRENT_GROUP}" "${WORKING_DIRECTORY}" "${UV_BIN}" <<'PY'
from pathlib import Path
import sys

template_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
values = {
    "USER": sys.argv[3],
    "GROUP": sys.argv[4],
    "WORKING_DIRECTORY": sys.argv[5],
    "UV_BIN": sys.argv[6],
}

content = template_path.read_text(encoding="utf-8")
for key, value in values.items():
    content = content.replace("{{" + key + "}}", value)

output_path.write_text(content, encoding="utf-8")
PY

echo "Rendered ${OUTPUT_PATH}"

if ((INSTALL_SYSTEM_UNIT)); then
  sudo install -m 0644 "${OUTPUT_PATH}" "/etc/systemd/system/${SERVICE_NAME}"
  sudo systemctl daemon-reload
  sudo systemctl enable "${SERVICE_NAME}"
  sudo systemctl restart "${SERVICE_NAME}"
  echo "Installed and restarted ${SERVICE_NAME}"
fi
