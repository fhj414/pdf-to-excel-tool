"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { DocumentReview } from "@/components/document-review";
import { getDocument } from "@/lib/api";
import type { DocumentResponse } from "@/lib/types";

type LoadPhase = "loading" | "polling" | "ready" | "failed";

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<LoadPhase>("loading");
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let consecutiveFailures = 0;

    async function load() {
      try {
        setPhase((current) => (current === "ready" ? current : "polling"));
        const result = await getDocument(params.id);
        if (active) {
          setDocument(result);
          setError(null);
          consecutiveFailures = 0;
          if (result.status === "processing") {
            timer = setTimeout(load, 2000);
          } else {
            setPhase("ready");
          }
        }
      } catch (loadError) {
        if (active) {
          consecutiveFailures += 1;
          const message = loadError instanceof Error ? loadError.message : "加载失败";
          setError(message);
          setPhase("failed");

          const backoffMs = Math.min(15000, 1200 * Math.max(1, consecutiveFailures));
          timer = setTimeout(load, backoffMs);
        }
      }
    }

    if (!params.id || Number.isNaN(Number(params.id))) {
      router.replace("/");
      return () => {};
    }

    void load();
    return () => {
      active = false;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [params.id, router, retryTick]);

  if (phase === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8]">
        <div className="rounded-3xl border border-line bg-white px-8 py-6 text-sm text-slate shadow-card">正在加载解析结果...</div>
      </main>
    );
  }

  if (phase === "failed") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8] px-4">
        <div className="w-full max-w-md rounded-3xl border border-red-200 bg-white px-8 py-7 text-sm shadow-card">
          <div className="text-red-700">{error ?? "加载失败"}</div>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              className="rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
              onClick={() => setRetryTick((tick) => tick + 1)}
            >
              立即重试
            </button>
            <button
              type="button"
              className="rounded-full border border-line bg-white px-5 py-2.5 text-sm font-medium text-ink transition hover:border-accent hover:text-accent"
              onClick={() => router.replace("/")}
            >
              回到主页
            </button>
          </div>
          <div className="mt-4 text-xs leading-6 text-slate">
            如果你刚上传完，这通常是网络或服务端短暂波动。页面会自动重试；也可以返回主页重新上传。
          </div>
        </div>
      </main>
    );
  }

  if (!document) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#eff4f8] px-4">
        <div className="w-full max-w-md rounded-3xl border border-line bg-white px-8 py-7 text-sm shadow-card">
          <div className="text-slate">文档不存在或已被清理。</div>
          <div className="mt-5">
            <button
              type="button"
              className="rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
              onClick={() => router.replace("/")}
            >
              回到主页
            </button>
          </div>
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
        <div className="w-full max-w-md rounded-3xl border border-red-200 bg-white px-8 py-7 text-center shadow-card">
          <div className="text-red-700">解析失败，请稍后重试或换一张更清晰的图片。</div>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <button
              type="button"
              className="rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
              onClick={() => router.replace("/")}
            >
              回到主页
            </button>
            <button
              type="button"
              className="rounded-full border border-line bg-white px-5 py-2.5 text-sm font-medium text-ink transition hover:border-accent hover:text-accent"
              onClick={() => setRetryTick((tick) => tick + 1)}
            >
              重新拉取结果
            </button>
          </div>
        </div>
      </main>
    );
  }

  return <DocumentReview initialDocument={document} />;
}
