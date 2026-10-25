#!/bin/bash
# Поднимает сервер LM Studio и прокси «Диктовка» (для launchd при входе в систему).
# Homebrew при обновлениях уносит python3, поэтому берём первый живой интерпретатор.
"$HOME/.lmstudio/bin/lms" server start >/dev/null 2>&1
for p in /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.12 /usr/local/bin/python3; do
  [ -x "$p" ] && exec "$p" "$(cd "$(dirname "$0")" && pwd)/proksi.py"
done
echo "нет python3 новее 3.9" >&2; exit 1
