# 班主任工作台 — 云端服务器部署

## 快速部署（推荐 Render.com，免费）

### 第 1 步：准备代码
确保 `cloud-server/server.js`、`cloud-server/package.json` 和项目根目录的 `teacher-workbench.html`、`libs/`、`manifest.json`、`sw.js` 在同一目录下。

### 第 2 步：部署到 Render.com
1. 访问 https://render.com 注册账号
2. 点击 "New +" → "Web Service"
3. 连接你的 GitHub 仓库（将整个项目上传到 GitHub）
4. 配置：
   - **Name**: teacher-workbench
   - **Runtime**: Node
   - **Build Command**: `cd cloud-server && npm install`
   - **Start Command**: `node cloud-server/server.js`
5. 点击 "Create Web Service"
6. 等待部署完成，获得网址（如 `https://teacher-workbench.onrender.com`）

### 第 3 步：配置工作台
1. 打开班主任工作台
2. 点击侧边栏的 **☁️ 云同步设置**
3. 输入 Render.com 的网址
4. 点击保存

### 第 4 步：手机端访问
在手机浏览器中打开同样的网址，即可通过云端实时同步数据。

---

## 其他部署选项

### Railway
https://railway.app → New Project → Deploy from GitHub → 同上配置

### 自建服务器
```bash
cd cloud-server
npm install
node server.js  # 默认端口 5000
# 或指定端口: PORT=8080 node server.js
```

---

## 技术说明
- 服务器使用 Express + Socket.IO，数据存储在 JSON 文件中
- 支持实时双向同步：任一设备保存后自动推送到其他设备
- 离线设备重连后自动拉取最新数据
- 默认账号: chenqi / 638893（可在 server.js 中修改）
