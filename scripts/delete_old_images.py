from pathlib import Path
import time
from collections import defaultdict

# img_dir = img_directory(目录)
#文件修改时间
# modification time(修改时间)

def clean_old_files(directory, pattern="*.png", max_age_hours=24):
    """
    清理目录下超过指定时长的图片文件
    参数：
        directory:          目录
        pattern:            文件匹配模式
        max_age_hours:      最大保留时长
    """
    img_dir = Path(directory)
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    expired_files = [] # expire 过期的

    if not img_dir.exists():
        print("目录不存在")
        return
    for f in img_dir.glob(pattern):
        if not f.is_file():
            continue
        age = now - f.stat().st_mtime
        if age >= max_age_seconds:
            expired_files.append((f,age))

    if not expired_files:
        print("没有过期的文件")
        return
    
    for f, age in expired_files:
        print(f"  {f.name}  (已存在 {age/3600:.1f} 小时)")
    print(f"共 {len(expired_files)} 个文件")

    answer = input("确认删除？(y/n)")
    if answer != "y":
        print("已取消")
        return

    for f, age in expired_files:
        f.unlink()
    print(f"清理完成，共删除 {len(expired_files)} 个文件")

def clean_by_count(directory, pattern="*.png", max_count=1000):
    """
    清理目录下超过指定数量的图片文件
    参数：
        directory:          目录
        pattern:            文件匹配模式
        max_count:          最大数量
    """
    img_dir = Path(directory)
    all_files = []
    if not img_dir.exists():
        print("目录不存在")
        return
    for f in img_dir.glob(pattern):
        if not f.is_file():
            continue
        all_files.append((f, f.stat().st_mtime))

    # 时间排序-最老的在最前面
    all_files.sort(key=lambda item: item[1])

    if len(all_files) <= max_count:
        print("文件数量未超限，无需清理")
        return
    delete_count = len(all_files) - max_count
    # 时间排序-最老的在最前面，删除最老的文件数
    to_delete = all_files[:delete_count]
    
    now = time.time()
    for f, mtime in to_delete:
        age = now - mtime
        print(f"  {f.name}  (已存在 {age/3600:.1f} 小时)")
    print(f"共 {len(all_files)} 个文件，超限 {delete_count} 个，将删除最老的 {len(to_delete)} 个")

    answer = input("确认删除？(y/n)")
    if answer != "y":
        print("已取消")
        return

    for f, mtime in to_delete:
        f.unlink()
    print(f"清理完成，共删除 {len(to_delete)} 个文件")

    # 提取图片名称并分组
def get_group_key(filename):
    """
    从文件名中提取分组键
    参数：
        filename: 文件名
    返回：
        分组键
    """
    parts = filename.split("_") # 以下划线进行分隔
    return "_".join(parts[1:3])
def clean_by_groups(directory, pattern="*.png"):
    """
    分组清理目录下图片文件
    参数：
        directory:          目录
        pattern:            文件匹配模式
    返回：
        按组清理，保留最新 keep_count 组，删除其余组
    """
    img_dir = Path(directory)
    groups = defaultdict(list)
    if not img_dir.exists():
        print("目录不存在")
        return
    for f in img_dir.glob(pattern):
        if not f.is_file():
            continue
        key = get_group_key(f.name)  # 提取组标识符
        groups[key].append(f)

    # 按组标识符排序
    sorted_groups = sorted(groups.items()) 
    keep_count = 1 # 保留最新一个组
    to_delete_groups = sorted_groups[:-keep_count] # 删除其他组

    # 扁平化处理，将所有文件展开为一个列表-用于循环删除
    to_delete = []
    for key, files in to_delete_groups:
        to_delete.extend(files)

    # 无需删除
    if not to_delete:
        print("没有文件需要清理")
        return
    # 预览
    for f in to_delete:
        print(f"  {f.name}")
    print(f"共 {len(groups)} 组，保留最新 {keep_count} 组，删除 {len(to_delete)} 个文件")

    # 确认流程
    answer = input("确认删除？(y/n)")
    if answer != "y":
        print("已取消")
        return
    # 执行删除
    for f in to_delete:
        f.unlink()
    print(f"清理完成，共删除 {len(to_delete)} 个文件")
if __name__ == "__main__":
    clean_old_files(
        directory="/home/robot/ros2_ws",
        pattern="*.png",
        max_age_hours=24,
    )
    clean_by_groups(
        directory="/home/robot/ros2_ws",
        pattern="*.png",
    )