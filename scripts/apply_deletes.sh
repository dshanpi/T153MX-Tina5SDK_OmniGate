#!/bin/sh
set -e
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET=${1:-$(pwd)}
if [ ! -d "$TARGET/.repo" ]; then
  echo "无效 Tina SDK 目录: $TARGET" >&2
  exit 1
fi
LIST="$SRC_DIR/meta/delete_list.txt"
if [ ! -s "$LIST" ]; then
  echo "delete_list empty"
  exit 0
fi
echo "将按 delete_list 删除文件。请确认列表已人工审查: $LIST"
printf '输入 YES 继续: '
read ans
[ "$ans" = YES ] || { echo "abort"; exit 1; }
while IFS= read -r rel || [ -n "$rel" ]; do
  [ -n "$rel" ] || continue
  case "$rel" in /*|*'..'*) echo "skip unsafe path: $rel" >&2; continue;; esac
  if [ -e "$TARGET/$rel" ] || [ -L "$TARGET/$rel" ]; then
    rm -f -- "$TARGET/$rel"
    echo "deleted $rel"
  fi
done < "$LIST"
echo "Done: deletes applied"
