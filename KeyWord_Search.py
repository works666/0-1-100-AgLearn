from pathlib import Path  #从模块来导入类，从语法上无法判断Path的类型，只有运行时才能知道它是类还是函数或者模块
import sys #直接导入模块


def search_files(folder: Path, keyword: str) -> str:  #folder: Path, keyword: str  类型注解
    files = sorted(folder.glob("*.txt"))#sorted（）将内容按字母排序并返回列表，列表里是path类对象,folder.glob("*.txt")返回一个生成器，生成器里是path类对象，glob()方法用于查找符合特定规则的文件路径名，"*.txt"表示查找所有以.txt结尾的文件
    #sorted()输入类型有iterable，输出类型是list，list里是path类对象，
    if not files: # files为空列表，not files为True
        #print(f"目录里没有 .txt 文件：{folder}")
        return "无资料"

    found_any = False
    result = ""
    for file_path in files:#对查找到的文件进行读取，splitlines()是字符串方法，用于将字符串按行分割成列表，返回一个列表，列表里的每个元素是文件的一行内容
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines() # 字符串方法，返回列表。read_text()是path类的方法，用于读取文件内容，encoding="utf-8"表示以utf-8编码读取文件，返回值是字符串
        except UnicodeDecodeError:
            print(f"无法按 UTF-8 读取：{file_path}")
            continue

        matches = [
            (line_number, line)
            for line_number, line in enumerate(lines, start=1) # enumerate()是内置函数，用于将可迭代对象组合为一个索引序列，同时列出数据和数据下标，start=1表示从1开始计数，返回值是一个迭代器，迭代器里是元组，元组里有两个元素，第一个元素是行号，第二个元素是行内容
            if keyword.casefold() in line.casefold()#casefold()是字符串方法，用于将字符串转换为小写，返回值是字符串，in是成员运算符，用于判断一个字符串是否包含另一个字符串，返回值是布尔值
        ]

        if matches:
            found_any = True
            #print(f"\n来源：{file_path}，共找到 {len(matches)} 条匹配内容：")
            result += f"\n来源：{file_path}\n"
            for line_number, line in matches:
                #print(f"  第 {line_number} 行：{line}")
                result += f"  第 {line_number} 行,内容为：{line}\n"

    if not found_any:
        #print(f"没有找到包含“{keyword}”的内容。")
        return "无资料"
    
    return result

def main() -> None:
   # if len(sys.argv) < 2:
      #  print('用法：python KeyWord-Search.py "搜索关键词"')
       # return 

    keyword = input("请输入搜索关键词：").strip()#sys.argv[1].strip()#strip()去掉字符串首尾的空格，sys.argv[1]获取命令行参数，[1]表示获取第一个参数，sys.argv[0]是脚本名
    if not keyword:
        print("搜索关键词不能为空。")
        return

    data_folder = Path(__file__).parent / "data"
    print(search_files(data_folder, keyword))


if __name__ == "__main__":
    main()