import "./globals.css";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PDF 全字段转 Excel 工具",
  description: "Upload PDF, review extracted fields, and export Excel."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

