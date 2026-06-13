#!/bin/bash
# ============================================================
# FreeLLMAPI 客户端构建脚本
# 解决 npm workspaces 下 @types/react-dom 和
# @vitejs/plugin-react 装不到正确位置的问题
# ============================================================
# 用法: 在 freellmapi 项目根目录执行
#   bash scripts/build-client.sh
# ============================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENT_DIR="$PROJECT_ROOT/client"

echo "🔄 开始构建 FreeLLMAPI 客户端..."
echo "项目目录: $PROJECT_ROOT"

if [ ! -d "$CLIENT_DIR" ]; then
  echo "❌ 错误: 找不到客户端目录 $CLIENT_DIR"
  exit 1
fi

cd "$CLIENT_DIR"

# Step 1: 检查 @types/react-dom
echo ""
echo "📦 Step 1/4: 检查 @types/react-dom..."
if [ ! -f "node_modules/@types/react-dom/index.d.ts" ]; then
  echo "   未找到，手动下载..."
  mkdir -p node_modules/@types/react-dom
  curl -sL "https://registry.npmjs.org/@types/react-dom/-/react-dom-19.2.3.tgz" \
    | tar xz --strip-components=1 -C node_modules/@types/react-dom
  echo "   ✅ 已安装"
else
  echo "   ✅ 已存在"
fi

# Step 2: 检查 @vitejs/plugin-react
echo ""
echo "📦 Step 2/4: 检查 @vitejs/plugin-react..."
if [ ! -f "node_modules/@vitejs/plugin-react/dist/index.js" ]; then
  echo "   未找到，手动下载..."
  mkdir -p node_modules/@vitejs/plugin-react
  curl -sL "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-6.0.2.tgz" \
    | tar xz --strip-components=1 -C node_modules/@vitejs/plugin-react
  echo "   ✅ 已安装"
else
  echo "   ✅ 已存在"
fi

# Step 3: 清理旧构建
echo ""
echo "🧹 Step 3/4: 清理旧构建..."
rm -rf dist
echo "   ✅ 已清理"

# Step 4: 构建
echo ""
echo "🔨 Step 4/4: 执行 npm run build..."
if npm run build 2>&1; then
  echo ""
  echo "✅ 构建成功！"
  echo "   输出目录: $CLIENT_DIR/dist/"
else
  exit $?
fi
