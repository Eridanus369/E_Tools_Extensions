import os
import shutil

def convert_to_msvc_utf8bom(file_path):
    with open(file_path, "rb") as f:
        raw = f.read()

    if raw.startswith(b"\xef\xbb\xbf"):
        print(f"[SKIP] {file_path}  → 已有UTF‑8‑BOM")
        return

    text = None
    try:
        text = raw.decode("utf‑8")
        print(f"[CONVERT] {file_path}  → 纯UTF‑8，添加BOM")
    except UnicodeDecodeError:
        # 尝试GBK
        try:
            text = raw.decode("gbk")
            print(f"[CONVERT] {file_path}  → GBK转UTF‑8‑BOM")
        except UnicodeDecodeError:
            try:
                text = raw.decode("gb2312")
                print(f"[CONVERT] {file_path}  → GB2312转UTF‑8‑BOM")
            except Exception as e:
                print(f"[ERROR] {file_path} 解码失败，跳过：{e}")
                return

    bak_path = file_path + ".bak"
    shutil.copy2(file_path, bak_path)
    print(f"[BACKUP] 备份：{bak_path}")

    out_bytes = b"\xef\xbb\xbf" + text.encode("utf‑8")
    with open(file_path, "wb") as fw:
        fw.write(out_bytes)
    print(f"[DONE] {file_path} 处理完成\n")


def scan_directory(root_dir):
    if not os.path.isdir(root_dir):
        print(f"[WARNING] 目录不存在：{root_dir}")
        return
    for root, _, filenames in os.walk(root_dir):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in (".cpp", ".h"):
                full = os.path.join(root, name)
                convert_to_msvc_utf8bom(full)


if __name__ == "__main__":
    target_dirs = [
        r"D:\blender\自制插件调试\E_Tools_Extensions\Extensions\ricci_uv\native\src",
        r"D:\blender\自制插件调试\E_Tools_Extensions\Extensions\ricci_uv\native\include"
    ]

    for folder in target_dirs:
        print(f"\n========== 扫描目录：{folder} ==========\n")
        scan_directory(folder)

    print("\n==== 全部处理结束 ====")
    print("提示：编译前删除build文件夹，重新cmake，C4819中文编码警告将消失。")
