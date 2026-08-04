#!/usr/bin/env python3
"""
班主任工作台 — 一键云端部署脚本
自动完成：GitHub 仓库创建 → 代码推送 → Render.com 部署配置
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
import subprocess
import time

# ============ CONFIG ============
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_NAME = "teacher-workbench"
REPO_DESC = "班主任工作台 - 支持云端同步的个人工作台应用"
GITHUB_API = "https://api.github.com"

# Files to include (relative to PROJECT_DIR)
INCLUDE_FILES = [
    ".gitignore",
    "package.json",
    "manifest.json",
    "sw.js",
    "teacher-workbench.html",
    "server.py",
    "workbench-launcher.py",
    "workbench.spec",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "libs/echarts.min.js",
    "libs/socket.io.min.js",
    "libs/xlsx.full.min.js",
    "cloud-server/.gitignore",
    "cloud-server/README.md",
    "cloud-server/package.json",
    "cloud-server/package-lock.json",
    "cloud-server/render.yaml",
    "cloud-server/server.js",
]

# ============ HELPERS ============

def api_request(method, url, token, data=None):
    """Make GitHub API request"""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TeacherWorkbench-Deploy/1.0"
    }
    if data is not None:
        data_bytes = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        data_bytes = None
    
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ HTTP {e.code}: {error_body[:300]}")
        return None
    except Exception as e:
        print(f"  ❌ 网络错误: {e}")
        return None


def get_github_username(token):
    """Get authenticated user info"""
    result = api_request("GET", f"{GITHUB_API}/user", token)
    if result and "login" in result:
        return result["login"]
    return None


def create_repo(token, username):
    """Create a new GitHub repository"""
    print(f"📦 创建 GitHub 仓库: {username}/{REPO_NAME}...")
    
    data = {
        "name": REPO_NAME,
        "description": REPO_DESC,
        "private": False,
        "auto_init": False,
    }
    
    result = api_request("POST", f"{GITHUB_API}/user/repos", token, data)
    if result and "html_url" in result:
        print(f"  ✅ 仓库已创建: {result['html_url']}")
        return result["html_url"], result["default_branch"]
    elif result and "message" in result and "already exists" in result["message"]:
        print(f"  ⚠️ 仓库已存在: https://github.com/{username}/{REPO_NAME}")
        return f"https://github.com/{username}/{REPO_NAME}", "main"
    else:
        print("  ❌ 创建仓库失败")
        return None, None


def read_file_binary(filepath):
    """Read file as binary"""
    with open(filepath, "rb") as f:
        return f.read()


def create_blobs(token, username):
    """Create blobs for all files via GitHub API"""
    print("📤 上传文件...")
    blobs = {}
    
    for rel_path in INCLUDE_FILES:
        full_path = os.path.join(PROJECT_DIR, rel_path)
        if not os.path.exists(full_path):
            print(f"  ⚠️ 文件不存在，跳过: {rel_path}")
            continue
        
        content = read_file_binary(full_path)
        content_b64 = base64.b64encode(content).decode("ascii")
        
        data = {
            "content": content_b64,
            "encoding": "base64"
        }
        
        result = api_request(
            "POST",
            f"{GITHUB_API}/repos/{username}/{REPO_NAME}/git/blobs",
            token,
            data
        )
        
        if result and "sha" in result:
            blobs[rel_path] = result["sha"]
            print(f"  ✅ {rel_path} ({len(content)} bytes)")
        else:
            print(f"  ❌ 上传失败: {rel_path}")
    
    return blobs


def create_tree(token, username, blobs, base_tree_sha=None):
    """Create a Git tree from blobs"""
    print("🌳 创建 Git tree...")
    
    tree_items = []
    for rel_path, blob_sha in blobs.items():
        # Normalize path separators
        normalized_path = rel_path.replace("\\", "/")
        tree_items.append({
            "path": normalized_path,
            "mode": "100644",  # Regular file
            "type": "blob",
            "sha": blob_sha
        })
    
    data = {"tree": tree_items}
    if base_tree_sha:
        data["base_tree"] = base_tree_sha
    
    result = api_request(
        "POST",
        f"{GITHUB_API}/repos/{username}/{REPO_NAME}/git/trees",
        token,
        data
    )
    
    if result and "sha" in result:
        print(f"  ✅ Tree SHA: {result['sha']}")
        return result["sha"]
    return None


def create_initial_commit(token, username, tree_sha):
    """Create the initial commit"""
    print("📝 创建初始 commit...")
    
    data = {
        "message": "班主任工作台 v2.0 - 支持云端同步",
        "tree": tree_sha,
    }
    
    result = api_request(
        "POST",
        f"{GITHUB_API}/repos/{username}/{REPO_NAME}/git/commits",
        token,
        data
    )
    
    if result and "sha" in result:
        print(f"  ✅ Commit SHA: {result['sha']}")
        return result["sha"]
    return None


def update_ref(token, username, branch, commit_sha):
    """Update branch reference to point to the commit"""
    print(f"🔗 更新分支 refs/heads/{branch}...")
    
    data = {
        "ref": f"refs/heads/{branch}",
        "sha": commit_sha,
    }
    
    result = api_request(
        "POST",
        f"{GITHUB_API}/repos/{username}/{REPO_NAME}/git/refs",
        token,
        data
    )
    
    if result:
        print(f"  ✅ 分支已更新")
        return True
    
    # Maybe the ref already exists, try PATCH
    print("  🔄 尝试更新已有分支...")
    result = api_request(
        "PATCH",
        f"{GITHUB_API}/repos/{username}/{REPO_NAME}/git/refs/heads/{branch}",
        token,
        data
    )
    
    if result:
        print(f"  ✅ 分支已更新")
        return True
    return False


def update_frontend_with_cloud_url(repo_url):
    """Update teacher-workbench.html with the Render.com URL placeholder"""
    html_path = os.path.join(PROJECT_DIR, "teacher-workbench.html")
    
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Add a note that the Render URL should be filled in
    render_placeholder = "https://YOUR-APP.onrender.com"
    
    if 'const CLOUD_SERVER_URL' in content:
        old_line = "const CLOUD_SERVER_URL = '';"
        new_line = f"// 部署后替换为 Render.com 提供的 URL\nconst CLOUD_SERVER_URL = '';  // 👈 替换为 https://xxx.onrender.com"
        content = content.replace(old_line, new_line)
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"  ✅ 已更新 teacher-workbench.html")


# ============ MAIN ============

def main():
    import argparse
    parser = argparse.ArgumentParser(description='班主任工作台云端部署')
    parser.add_argument('--token', '-t', help='GitHub Personal Access Token')
    args = parser.parse_args()
    
    print("=" * 60)
    print("  班主任工作台 — 一键云端部署")
    print("=" * 60)
    print()
    
    # 1. Get token
    token = args.token
    if not token:
        print("📋 第 1 步：获取 GitHub Token")
        print("-" * 40)
        print("""
如果没有 GitHub Token，请按以下步骤创建：
  1. 打开 https://github.com/settings/tokens
  2. 点击 "Generate new token" → "Generate new token (classic)"
  3. Note 填 "teacher-workbench"，Expiration 选 "No expiration"
  4. 勾选以下权限：
     ✅ repo (全部勾选)
     ✅ workflow
  5. 点击 "Generate token"
  6. 复制生成的 token（只显示一次！）
""")
        token = input("请输入 GitHub Token: ").strip()
    if not token:
        print("❌ Token 不能为空，已取消")
        return
    
    # 2. Verify token
    print("\n🔑 验证 Token...")
    username = get_github_username(token)
    if not username:
        print("❌ Token 无效，请检查后重试")
        return
    print(f"  ✅ 已认证为: {username}")
    
    # 3. Create repo
    print()
    repo_url, default_branch = create_repo(token, username)
    if not repo_url:
        return
    
    # 4. Upload files via Git Data API
    print()
    blobs = create_blobs(token, username)
    if not blobs:
        print("❌ 文件上传失败")
        return
    
    # 5. Create tree
    tree_sha = create_tree(token, username, blobs)
    if not tree_sha:
        return
    
    # 6. Create commit
    commit_sha = create_initial_commit(token, username, tree_sha)
    if not commit_sha:
        return
    
    # 7. Update branch
    branch = default_branch or "main"
    if not update_ref(token, username, branch, commit_sha):
        # Try "master" branch
        branch = "master"
        if not update_ref(token, username, branch, commit_sha):
            return
    
    # 8. Success!
    print()
    print("=" * 60)
    print("  🎉 GitHub 部署完成！")
    print("=" * 60)
    print(f"""
仓库地址: {repo_url}

📋 第 2 步：部署到 Render.com（免费 24 小时运行）
  1. 打开 https://render.com → 用 GitHub 账号登录
  2. 点击 "New +" → "Web Service"
  3. 连接你的 GitHub 账号，选择 {REPO_NAME} 仓库
  4. Render 会自动读取 cloud-server/render.yaml 配置
  5. 点击 "Create Web Service" 

⏱️ 部署需要 3-5 分钟，完成后 Render 会提供 URL
   例如: https://teacher-workbench.onrender.com

📋 第 3 步：配置工作台连接云端
  1. 打开班主任工作台
  2. 点击侧边栏 "☁️ 云同步设置"
  3. 填入 Render.com 提供的 URL
  4. 保存 → 完成！
""")
    
    # Update frontend with a comment
    update_frontend_with_cloud_url(repo_url)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 已取消部署")
    except Exception as e:
        print(f"\n❌ 部署出错: {e}")
        import traceback
        traceback.print_exc()
