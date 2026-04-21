"use client";

import { useRef, useState } from "react";

interface UploadDropzoneProps {
  onFileSelected: (file: File) => Promise<void>;
  onDemoSelected: () => Promise<void>;
  loading: boolean;
}

export function UploadDropzone({ onFileSelected, onDemoSelected, loading }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) {
      return;
    }
    await onFileSelected(file);
  }

  return (
    <div className="rounded-[32px] border border-line bg-white/90 p-8 shadow-card backdrop-blur">
      <div
        className={`rounded-[28px] border-2 border-dashed p-10 text-center transition ${
          dragActive ? "border-accent bg-emerald-50" : "border-line bg-panel"
        }`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setDragActive(false);
        }}
        onDrop={async (event) => {
          event.preventDefault();
          setDragActive(false);
          await handleFiles(event.dataTransfer.files);
        }}
      >
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-accent">PDF Extraction Workspace</p>
        <h2 className="mt-4 text-3xl font-semibold text-ink">拖拽 PDF 或图片到这里，自动转成可校对 Excel 数据</h2>
        <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate">
          支持 PDF、发票截图、扫描件照片，多页文档、字段坐标、表格抽取、金额日期校验和在线修订。上传后会自动跳转到结果页。
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <button
            type="button"
            className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => inputRef.current?.click()}
            disabled={loading}
          >
            {loading ? "处理中..." : "选择 PDF / 图片"}
          </button>
          <button
            type="button"
            className="rounded-full border border-line bg-white px-6 py-3 text-sm font-medium text-ink transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
            onClick={onDemoSelected}
            disabled={loading}
          >
            使用示例 PDF
          </button>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/png,image/jpeg,image/webp,image/bmp,image/tiff"
          className="hidden"
          onChange={async (event) => {
            await handleFiles(event.target.files);
            event.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
