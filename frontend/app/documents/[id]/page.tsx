"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { DocumentReview } from "@/components/document-review";
import { getDocument } from "@/lib/api";
import type { DocumentResponse } from "@/lib/types";

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function load() {
      try {
        const result = await getDocument(params.id);
        if (active) {
          setDocument(result);
          setError(null);
          if (result.status === "processing") {
            timer = setTimeout(load, 2000);
          }
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "加载失败");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      active = false;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [params.id]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8]">
        <div className="rounded-3xl border border-line bg-white px-8 py-6 text-sm text-slate shadow-card">正在加载解析结果...</div>
      </main>
    );
  }

  if (error || !document) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8] px-4">
        <div className="rounded-3xl border border-red-200 bg-white px-8 py-6 text-sm text-red-700 shadow-card">
          {error ?? "文档不存在"}
        </div>
      </main>
    );
  }

  if (document.status === "processing") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8] px-4">
        <div className="max-w-md rounded-3xl border border-line bg-white px-8 py-7 text-center shadow-card">
          <p className="text-sm font-semibold uppercase tracking-[0.26em] text-accent">Processing</p>
          <h1 className="mt-3 text-2xl font-semibold text-ink">正在解析文档</h1>
          <p className="mt-3 text-sm leading-7 text-slate">
            上传已经成功，后台正在抽取表格和字段。页面会自动刷新，复杂图片通常需要几十秒。
          </p>
        </div>
      </main>
    );
  }

  if (document.status === "failed") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8] px-4">
        <div className="max-w-md rounded-3xl border border-red-200 bg-white px-8 py-7 text-center text-red-700 shadow-card">
          解析失败，请稍后重试或换一张更清晰的图片。
        </div>
      </main>
    );
  }

  return <DocumentReview initialDocument={document} />;
}
