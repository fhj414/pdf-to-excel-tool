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

    async function load() {
      try {
        const result = await getDocument(params.id);
        if (active) {
          setDocument(result);
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

  return <DocumentReview initialDocument={document} />;
}
