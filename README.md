# PDF 全字段转 Excel 工具

一个可以本地直接启动的 PDF 解析 Web 应用，支持：

- 上传多页 PDF
- 上传图片文件（PNG/JPG/JPEG/WEBP/BMP/TIFF）
- 自动判断数字型 PDF / 扫描型 PDF
- 数字型 PDF 使用 `PyMuPDF + pdfplumber` 提取文本块、表格、坐标
- 扫描型 PDF 预留 OCR 接口，并输出统一字段结构
- 在线校对字段与表格
- 规则校验与低置信提示
- 导出三张 Excel Sheet

## 技术栈

- 前端：Next.js + TypeScript + Tailwind CSS
- 后端：FastAPI + Python 3.11
- PDF：PyMuPDF、pdfplumber
- Excel：pandas、openpyxl
- 存储：SQLite

## 目录结构

```text
.
├── backend
│   ├── app
│   │   ├── routers
│   │   ├── services
│   │   └── ...
├── frontend
│   ├── app
│   ├── components
│   └── lib
├── scripts
├── Dockerfile
└── docker-compose.yml
```

## 快速启动

### 方式一：本地启动

1. 复制环境变量

```bash
cp .env.example .env
```

2. 启动后端

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如果本机没有 `python3.11`，也可以直接改用 `python3`。

3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

4. 打开

- 前端：[http://localhost:3000](http://localhost:3000)
- 后端文档：[http://localhost:8000/docs](http://localhost:8000/docs)

如果前端改跑在 `3001`，默认 CORS 也已放行 `http://localhost:3001` 和 `http://127.0.0.1:3001`。

### 方式二：一键脚本

```bash
chmod +x scripts/start-local.sh
./scripts/start-local.sh
```

### 方式三：Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

## 主要接口

- `POST /api/documents/upload`：上传并解析 PDF 或图片
- `POST /api/demo/generate`：生成示例 PDF 并自动解析
- `GET /api/documents/{document_id}`：查询解析结果
- `PUT /api/documents/{document_id}/fields/{field_index}`：修改字段
- `GET /api/documents/{document_id}/export`：导出 Excel
- `GET /api/health`：健康检查

## 解析流程

后端统一入口为 `parse_pdf()`，内部拆分为：

- `detect_pdf_type()`
- `extract_text_blocks()`
- `extract_tables()`
- `normalize_fields()`
- `validate_fields()`
- `export_excel()`

## 统一字段 Schema

```json
{
  "field_key": "",
  "field_value": "",
  "confidence": 0.0,
  "bbox": [0, 0, 0, 0],
  "page_no": 1,
  "source_type": "text"
}
```

## 统一表格 Schema

```json
{
  "columns": [],
  "rows": [],
  "page_no": 1,
  "confidence": 0.0
}
```

## OCR 扩展点

当前扫描型 PDF 已保留 `run_ocr_placeholder()` 入口，后续可接：

- PaddleOCR
- Tesseract
- 云 OCR 服务

只需要保证最终仍输出统一字段与表格结构即可。

## MVP 说明

当前版本优先保证：

- 数字型 PDF 可直接抽取文本与表格
- 图片上传会自动转单页 PDF，再复用统一解析链路
- 扫描型 PDF 不会报错，并能返回统一结果与待接入 OCR 的提示
- 在线修订、规则校验、Excel 导出完整可用

后续可继续扩展模板学习、票据类型识别、字段映射训练与 OCR。
