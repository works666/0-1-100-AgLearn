from pathlib import Path

folderpath = Path.cwd() / "data"  # 确保当前目录是项目根目录
sources = [
    {"source": file.name}
    for pattern in ["*.txt", "*.pdf"]  # 假设文件是 .txt 或 .pdf 格式
    for file in folderpath.glob(pattern)
]
print(sources)