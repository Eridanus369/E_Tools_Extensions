# -*- coding: utf-8 -*-
import bpy

REPO_NAME = "E‑Tools Extensions"
REPO_MODULE = "e_tools_extensions"
REPO_URL = "https://eridanus369.github.io/E_Tools_Extensions/index.json"

def find_repo():
    for repo in bpy.context.preferences.extensions.repos:
        if repo.remote_url == REPO_URL:
            return repo
    return None

def add_repo():
    repo = find_repo()
    if repo is not None:
        print(f"仓库已存在: {repo.name}")
        return repo
    repo = bpy.context.preferences.extensions.repos.new(
        name=REPO_NAME,
        module=REPO_MODULE,
        remote_url=REPO_URL,
        source='USER',
    )
    repo.use_cache = True
    print(f"已添加仓库: {repo.name} ({REPO_URL})")
    return repo

def sync_repo(repo):
    bpy.ops.extensions.repo_sync(repo_directory=repo.directory)
    print("仓库已同步，插件列表已刷新。")

def main():
    repo = add_repo()
    if repo is not None:
        sync_repo(repo)
        wm = bpy.data.window_managers["WinMan"]
        wm.extension_use_filter = True
        wm.extension_type = 'ADDON'
        wm.extension_repo_filter = REPO_MODULE
        print(f"已启用筛选并切换至仓库: {REPO_MODULE}")
        bpy.ops.wm.save_userpref()
        print("完成！偏好设置已保存。可打开 偏好设置 → Get Extensions 查看插件。")

if __name__ == "__main__":
    main()
