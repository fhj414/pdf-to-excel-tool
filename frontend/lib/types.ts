export type SourceType = "text" | "table" | "ocr" | "rule";

export interface FieldItem {
  field_key: string;
  field_value: string;
  confidence: number;
  bbox: [number, number, number, number];
  page_no: number;
  source_type: SourceType;
}

export interface TableItem {
  columns: string[];
  rows: Record<string, string>[];
  page_no: number;
  confidence: number;
}

export interface ValidationIssue {
  rule: string;
  message: string;
  severity: "warning" | "error";
  page_no?: number | null;
  field_key?: string | null;
  table_row?: number | null;
}

export interface PagePreview {
  page_no: number;
  image_url: string;
  width: number;
  height: number;
}

export interface ParseStats {
  field_count: number;
  table_count: number;
  low_confidence_count: number;
  error_count: number;
}

export interface ParseResult {
  pdf_type: "digital" | "scanned";
  fields: FieldItem[];
  tables: TableItem[];
  validation_issues: ValidationIssue[];
  pages: PagePreview[];
  stats: ParseStats;
}

export interface DocumentResponse {
  id: number;
  filename: string;
  pdf_type: string;
  page_count: number;
  status: string;
  created_at?: string;
  updated_at?: string;
  parse_result: ParseResult;
}

