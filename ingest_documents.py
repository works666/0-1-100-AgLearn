import json
from pathlib import Path
from typing import Any
from pypdf import PdfReader
import re


PROJECT_DIR = Path(__file__).resolve().parent#resolve()绝对路径，若不加，运行时表示相对路径，可能基于终端所在文件夹
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_FILE = PROJECT_DIR / "chunks.jsonl"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
BOUNDARIES = ("\n", "。", "！", "？", "；")


def split_text(text: str) -> list[str]:#这个函数将文本分割成多个块，每个块的大小不超过CHUNK_SIZE，并且在块之间有一定的重叠CHUNK_OVERLAP。它还会尝试在指定的边界字符处进行分割，以确保块的完整性。
    text = text.strip()
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            search_start = start + CHUNK_SIZE // 2
            boundary = max(text.rfind(mark, search_start, end) for mark in BOUNDARIES)
            if boundary >= search_start:
                end = boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks

def clean_pdf_text(text: str) -> str:
    # PDF 常把相邻汉字拆成多行；合并汉字之间的空白
    text = re.sub(
        r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])",
        "",
        text,
    )

    # 去掉中文标点前后的多余空白
    text = re.sub(r"\s+([，。；：！？、）】》”])", r"\1", text)
    text = re.sub(r"([（【《“])\s+", r"\1", text)

    # 收拢剩余连续空格，但保留可能有意义的段落换行
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()


def make_records(path: Path) -> list[dict[str, Any]]:
    '''
        这个函数根据文件的后缀名（.txt或.pdf）来处理文件内容，并将其分割成多个记录。每个记录是一个字典，包含文本块、源文件名和页码（如果是PDF）。如果文件没有可提取的文本，会抛出相应的错误。
    '''
    records: list[dict[str, Any]] = []

    if path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8-sig")
        for chunk in split_text(text):
            records.append({"text": chunk, "source": path.name, "page": None})
    elif path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        for page_number, page in enumerate(reader.pages, start=1):
            text = clean_pdf_text(page.extract_text() or "") #清洗数据
            for chunk in split_text(text):
                records.append(
                    {"text": chunk, "source": path.name, "page": page_number}
                )

    if not records:
        if path.suffix.lower() == ".pdf":
            raise ValueError(
                f"{path.name} has no extractable text; scanned PDFs need OCR."
            )
        raise ValueError(f"{path.name} contains no text.")

    return records


def main() -> None:
    files = sorted(
        path
        for path in DATA_DIR.iterdir()#iterdir()返回一个迭代器，生成目录下的所有文件和子目录的路径对象
        if path.is_file() and path.suffix.lower() in {".txt", ".pdf"}#is_file()判断路径是否为文件，suffix.lower()获取文件后缀名并转换为小写
    )
    if not files:
        raise FileNotFoundError(f"No TXT or PDF files found in {DATA_DIR}")

    records: list[dict[str, Any]] = []
    for path in files:
        records.extend(make_records(path))

    for chunk_id, record in enumerate(records, start=1):
        record["chunk_id"] = chunk_id

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    sources = {record["source"] for record in records}
    pdf_chunks = sum(
        record["page"] is not None and record["source"].lower().endswith(".pdf")
        for record in records
    )
    print(
        f"Wrote {len(records)} chunks from {len(sources)} files to {OUTPUT_FILE.name} "
        f"({pdf_chunks} PDF chunks with page numbers)."
    )


if __name__ == "__main__":
    main()
