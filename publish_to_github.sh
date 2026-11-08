#!/bin/zsh
set -e
cd "$(dirname "$0")"

if [ -z "$1" ]; then
  echo "用法: ./publish_to_github.sh <GitHub 仓库地址>"
  echo "例如: ./publish_to_github.sh git@github.com:your-name/autohome-spec-exporter.git"
  exit 1
fi

REPO_URL="$1"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO_URL"
else
  git remote add origin "$REPO_URL"
fi

git push -u origin main
echo ""
echo "已推送到 GitHub。Actions 会自动开始构建："
echo "$REPO_URL/actions"
