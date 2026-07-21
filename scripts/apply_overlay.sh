#!/bin/sh
set -e
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET=${1:-$(pwd)}
if [ ! -d "$TARGET/.repo" ]; then
  echo "无效 Tina SDK 目录: $TARGET" >&2
  exit 1
fi
echo "[OVERLAY] copy files from $SRC_DIR/overlay to $TARGET"
(cd "$SRC_DIR/overlay" && tar -cpf - .) | (cd "$TARGET" && tar -xpf -)
echo "Done: overlay copied. 删除动作未执行；如需删除，先审查 meta/delete_list.txt，再运行 scripts/apply_deletes.sh"
