import os
import zipfile
import shutil
from datetime import datetime

IGNORE_EXT = {".obj", ".pdb", ".ilk", ".exe", ".bak", ".log", ".tmp"}
IGNORE_DIR = {"build", "build_release", "bin", "out", ".cache"}

def zip_directory_filtered(src_dir, zip_output_path):
    with zipfile.ZipFile(zip_output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIR]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in IGNORE_EXT:
                    continue
                full_path = os.path.join(root, fname)
                arcname = os.path.relpath(full_path, src_dir)
                zf.write(full_path, arcname)
    print(f"✅ 打包完成（已过滤编译临时文件）：{zip_output_path}")

def remove_dir_safe(target_path):
    if os.path.isdir(target_path):
        try:
            shutil.rmtree(target_path)
            print(f"🗑️ 已删除目录：{target_path}")
        except Exception as e:
            print(f"❌ 删除失败 {target_path} : {e}")
    else:
        print(f"ℹ️ 目录不存在，跳过删除：{target_path}")

if __name__ == "__main__":
    source_folder = r"D:\blender\自制插件调试\E_Tools_Extensions\Extensions\ricci_uv"
    target_del_folder = r"D:\blender\extensions\user_default\ricci_uv"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_zip = os.path.join(
        r"D:\blender\自制插件调试\E_Tools_Extensions\Extensions",
        f"ricci_uv_backup_clean_{timestamp}.zip"
    )

    if not os.path.isdir(source_folder):
        print(f"❌ 源码目录不存在：{source_folder}")
    else:
        # 1.先备份打包
        zip_directory_filtered(source_folder, output_zip)
        # 2.再删除Blender插件目录
        remove_dir_safe(target_del_folder)
    print("\n全部任务执行完毕")
