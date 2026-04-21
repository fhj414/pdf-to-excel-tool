"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { getAssetUrl, getExportUrl, updateField } from "@/lib/api";
import type { DocumentResponse, FieldItem } from "@/lib/types";

interface DocumentReviewProps {
  initialDocument: DocumentResponse;
}

export function DocumentReview({ initialDocument }: DocumentReviewProps) {
  const [document, setDocument] = useState(initialDocument);
  const [activeFieldIndex, setActiveFieldIndex] = useState<number | null>(0);
  const [savingIndex, setSavingIndex] = useState<number | null>(null);

  const activeField = activeFieldIndex !== null ? document.parse_result.fields[activeFieldIndex] : null;
  const activePage = useMemo(() => {
    const targetPageNo = activeField?.page_no ?? 1;
    return document.parse_result.pages.find((page) => page.page_no === targetPageNo) ?? document.parse_result.pages[0];
  }, [activeField, document.parse_result.pages]);

  async function persistField(index: number, field: FieldItem) {
    try {
      setSavingIndex(index);
      const nextDocument = await updateField(document.id, index, field.field_value);
      setDocument(nextDocument);
    } finally {
      setSavingIndex(null);
    }
  }

  return (
    <div className="min-h-screen bg-[#eff4f8]">
      <div className="mx-auto max-w-[1600px] px-4 py-6 lg:px-8">
        <div className="mb-6 flex flex-col gap-4 rounded-[28px] border border-line bg-white px-6 py-5 shadow-card lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-accent">Document Review</p>
            <h1 className="mt-2 text-2xl font-semibold text-ink">{document.filename}</h1>
            <p className="mt-2 text-sm text-slate">
              {document.pdf_type === "digital" ? "数字型 PDF" : "扫描型 PDF"} · {document.page_count} 页 ·{" "}
              {document.parse_result.stats.field_count} 个字段 · {document.parse_result.stats.table_count} 张表格
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              href="/"
              className="rounded-full border border-line bg-white px-5 py-3 text-sm font-medium text-ink transition hover:border-accent hover:text-accent"
            >
              返回上传页
            </Link>
            <a
              href={getExportUrl(document.id)}
              className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              导出 Excel
            </a>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
          <section className="rounded-[28px] border border-line bg-white p-4 shadow-card">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-ink">PDF 预览</h2>
              <span className="rounded-full bg-panel px-3 py-1 text-xs font-medium text-slate">
                第 {activePage?.page_no ?? 1} 页
              </span>
            </div>

            {activePage ? (
              <div className="relative overflow-hidden rounded-[20px] border border-line bg-panel p-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getAssetUrl(activePage.image_url)}
                  alt={`Page ${activePage.page_no}`}
                  className="w-full rounded-[14px] border border-line bg-white"
                />
                {activeField && activeField.page_no === activePage.page_no && hasDrawableBbox(activeField) ? (
                  <div
                    className="pointer-events-none absolute border-2 border-accent bg-emerald-400/15"
                    style={bboxToStyle(activeField.bbox, activePage.width, activePage.height)}
                  />
                ) : null}
              </div>
            ) : (
              <div className="rounded-[20px] border border-dashed border-line bg-panel p-10 text-center text-sm text-slate">
                暂无页面预览
              </div>
            )}
          </section>

          <section className="space-y-6">
            <div className="rounded-[28px] border border-line bg-white p-5 shadow-card">
              <h2 className="text-lg font-semibold text-ink">规则校验</h2>
              <div className="mt-4 space-y-3">
                {document.parse_result.validation_issues.length === 0 ? (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    当前未发现规则错误。
                  </div>
                ) : (
                  document.parse_result.validation_issues.map((issue, index) => (
                    <div
                      key={`${issue.rule}-${index}`}
                      className={`rounded-2xl border px-4 py-3 text-sm ${
                        issue.severity === "error"
                          ? "border-red-200 bg-red-50 text-red-700"
                          : "border-amber-200 bg-amber-50 text-amber-700"
                      }`}
                    >
                      <p className="font-medium">{issue.rule}</p>
                      <p className="mt-1">{issue.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-[28px] border border-line bg-white p-5 shadow-card">
              <h2 className="text-lg font-semibold text-ink">字段列表</h2>
              <div className="mt-4 max-h-[520px] space-y-3 overflow-auto pr-1">
                {document.parse_result.fields.map((field, index) => (
                  <button
                    key={`${field.field_key}-${index}`}
                    type="button"
                    onClick={() => setActiveFieldIndex(index)}
                    className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                      activeFieldIndex === index
                        ? "border-accent bg-emerald-50"
                        : field.confidence < 0.6
                          ? "border-red-200 bg-red-50"
                          : field.confidence < 0.75
                            ? "border-amber-200 bg-amber-50"
                            : "border-line bg-white hover:border-accent/40"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-ink">{field.field_key}</p>
                        <input
                          value={field.field_value}
                          onChange={(event) => {
                            const nextDocument = structuredClone(document);
                            nextDocument.parse_result.fields[index].field_value = event.target.value;
                            setDocument(nextDocument);
                          }}
                          onBlur={async () => {
                            await persistField(index, document.parse_result.fields[index]);
                          }}
                          className="mt-2 w-full rounded-xl border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent"
                        />
                        <p className="mt-2 text-xs text-slate">
                          Page {field.page_no} · {field.source_type} · confidence {(field.confidence * 100).toFixed(0)}%
                        </p>
                      </div>
                      <div className="text-xs text-slate">{savingIndex === index ? "保存中..." : ""}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[28px] border border-line bg-white p-5 shadow-card">
              <h2 className="text-lg font-semibold text-ink">抽取表格</h2>
              <div className="mt-4 space-y-4">
                {document.parse_result.tables.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-line bg-panel px-4 py-4 text-sm text-slate">
                    当前文档没有抽取到结构化表格。
                  </div>
                ) : (
                  document.parse_result.tables.map((table, tableIndex) => (
                    <div key={`table-${tableIndex}`} className="overflow-hidden rounded-2xl border border-line">
                      <div className="flex items-center justify-between border-b border-line bg-panel px-4 py-3">
                        <p className="text-sm font-semibold text-ink">表格 {tableIndex + 1}</p>
                        <span className="text-xs text-slate">
                          第 {table.page_no} 页 · confidence {(table.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="overflow-auto">
                        <table className="min-w-full border-collapse text-sm">
                          <thead>
                            <tr className="bg-white">
                              {table.columns.map((column) => (
                                <th key={column} className="border-b border-line px-4 py-3 text-left font-medium text-slate">
                                  {column}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {table.rows.map((row, rowIndex) => (
                              <tr key={`row-${rowIndex}`} className="odd:bg-white even:bg-panel/50">
                                {table.columns.map((column) => (
                                  <td key={`${rowIndex}-${column}`} className="border-b border-line px-4 py-3 text-ink">
                                    {row[column] ?? ""}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function hasDrawableBbox(field: FieldItem) {
  return field.bbox.some((value) => value > 0);
}

function bboxToStyle(bbox: [number, number, number, number], pageWidth: number, pageHeight: number) {
  const [x0, y0, x1, y1] = bbox;
  return {
    left: `calc(${(x0 / pageWidth) * 100}% + 12px)`,
    top: `calc(${(y0 / pageHeight) * 100}% + 12px)`,
    width: `calc(${((x1 - x0) / pageWidth) * 100}% - 24px)`,
    height: `calc(${((y1 - y0) / pageHeight) * 100}% - 24px)`
  };
}
