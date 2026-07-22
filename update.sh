#!/bin/bash
# 一鍵更新 irl-server-bot：拉最新程式碼、重建 image、重啟 container
set -euo pipefail

cd "$(dirname "$0")"

echo "==> 拉取最新程式碼"
git pull

echo "==> 重新建置 Docker image"
docker build -t irl-server-bot .

echo "==> 停止並移除舊 container"
docker stop irl-server-bot 2>/dev/null || true
docker rm irl-server-bot 2>/dev/null || true

echo "==> 啟動新 container"
docker run -d --name irl-server-bot --restart=always --env-file .env irl-server-bot

echo "==> 清理未使用的舊 image"
docker image prune -f

echo "==> 完成，最新狀態："
docker ps --filter "name=irl-server-bot"
echo "==> 最近 log："
sleep 3
docker logs --tail 20 irl-server-bot
