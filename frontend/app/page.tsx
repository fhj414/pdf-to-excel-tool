"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { UploadDropzone } from "@/components/upload-dropzone";
import { createDemoDocument, uploadPdf } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    try {
      setLoading(true);
      setError(null);
      const documentId = await uploadPdf(file);
      router.push(`/documents/${documentId}`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "上传失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleDemo() {
    try {
      setLoading(true);
      setError(null);
      const documentId = await createDemoDocument();
      router.push(`/documents/${documentId}`);
    } catch (demoError) {
      setError(demoError instanceof Error ? demoError.message : "示例生成失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-10 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-[0.32em] text-accent">B2B PDF Extraction</p>
          <h1 className="mt-4 max-w-4xl text-5xl font-semibold leading-tight text-ink">
            PDF 全字段转 Excel
            <span className="block text-slate">上传、抽取、校对、校验、导出，一次走完。</span>
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-8 text-slate">
            面向订单、对账单、发票、采购单、扫描截图等文档的结构化提取工具。MVP 优先保证结果可用，并预留 OCR 与模板学习扩展位。
          </p>
        </div>

        <UploadDropzone onFileSelected={handleUpload} onDemoSelected={handleDemo} loading={loading} />

        {error ? (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : null}

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            ["数字型 / 扫描型识别", "支持 PDF 与图片上传，先判断文本型还是扫描型，再走对应流程。"],
            ["统一字段 Schema", "所有结果统一输出 field_key、value、bbox、page_no、confidence。"],
            ["Excel 三 Sheet 导出", "原始明细、结构化字段、错误与低置信字段一次导出。"]
          ].map(([title, desc]) => (
            <div key={title} className="rounded-[24px] border border-line bg-white/80 p-5 shadow-card">
              <h2 className="text-lg font-semibold text-ink">{title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
