import {
  Calculator, ClipboardCheck, Copy, FileScan, FileSpreadsheet, GitCompareArrows, History, LayoutDashboard, Lock, ScanText,
  ShieldCheck, Users, type LucideIcon,
} from "lucide-react";

export const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: ScanText, title: "OCR & text extraction", body: "Digital PDFs are read directly with PyMuPDF; scans and photos go through Tesseract OCR one page at a time, with confidence scores." },
  { icon: FileScan, title: "Structured field extraction", body: "Supplier, buyer, GSTINs, dates, PO references, line items and tax summaries become schema-validated JSON. Unclear fields stay empty and are flagged — never guessed." },
  { icon: Calculator, title: "Deterministic GST validation", body: "Line maths, taxable totals, CGST/SGST vs IGST regime, grand totals and GSTIN check digits — calculated with exact decimals, not an LLM." },
  { icon: Copy, title: "Duplicate detection", body: "Same supplier and invoice number, identical file checksums, or matching amount and date are surfaced with an explanation — nothing is silently discarded." },
  { icon: GitCompareArrows, title: "Purchase-order matching", body: "Line-by-line comparison of quantity, unit price, tax rate and amount with configurable tolerances. Extra and missing items are listed explicitly." },
  { icon: ClipboardCheck, title: "Human approval workflow", body: "Review, correct and submit. Single or multi-level approval by amount, no self-approval, mandatory rejection reasons, and critical errors block approval." },
  { icon: History, title: "Tamper-resistant audit trail", body: "Uploads, extractions, corrections, decisions, exports and permission changes are recorded with actor, time and context. Audit entries cannot be edited." },
  { icon: LayoutDashboard, title: "Role-based dashboards", body: "Admins, accountants and approvers each get the metrics they act on — all computed live from the database." },
  { icon: FileSpreadsheet, title: "Excel reporting", body: "Invoice register, line details, supplier, validation exception, PO matching, approval history and monthly summary reports with totals." },
  { icon: Users, title: "Multi-company isolation", body: "Every query is scoped to the signed-in user's company on the server. IDs from other companies simply return “not found”." },
  { icon: Lock, title: "Secure document handling", body: "Content-sniffed uploads, size and page limits, server-generated storage paths and authorised downloads only." },
  { icon: ShieldCheck, title: "Optional, guarded AI", body: "Runs fully without any model. An optional local Qwen 2.5 0.5B (Ollama) may fill missing identifiers — only if the value literally appears in the document." },
];

export const STEPS = [
  { title: "Upload", body: "Drop a PDF, JPG or PNG invoice. The file is verified by content, checksummed and stored privately." },
  { title: "Read", body: "Text is extracted from digital PDFs or recognised with OCR for scans, page by page." },
  { title: "Extract", body: "Rules turn text into structured, typed fields. Missing or uncertain values are marked for review." },
  { title: "Check", body: "Exact-decimal validation, duplicate detection and purchase-order matching run automatically." },
  { title: "Review", body: "An accountant compares extracted data with the original side by side and corrects anything wrong." },
  { title: "Approve", body: "Approvers decide with full context. Every action lands in the audit log and the dashboards update." },
];

export const PLANS = [
  { name: "Starter", price: "₹0", period: "self-hosted", tagline: "For evaluation and small teams running it on their own machine.",
    features: ["All core modules", "Rule-based extraction + Tesseract OCR", "SQLite or your own PostgreSQL", "Community support"], cta: "Try the demo" },
  { name: "Business", price: "₹4,999", period: "per month", tagline: "Hosted workspace for growing finance teams.", highlight: true,
    features: ["Up to 2,000 invoices / month", "Multi-level approvals", "Supabase PostgreSQL & storage", "Excel reporting suite", "Email support"], cta: "Contact sales" },
  { name: "Enterprise", price: "Custom", period: "implementation", tagline: "Custom extraction templates and accounting integrations.",
    features: ["Supplier-specific templates", "ERP / Tally / Zoho Books integration", "SSO & retention policies", "On-premise or private cloud", "Dedicated onboarding"], cta: "Talk to us" },
];

export const FAQS = [
  { q: "Does LedgerFlow need an AI model or a GPU to work?", a: "No. Extraction is rule-based by default and validation is pure Python with exact decimals. An optional small local model (Qwen 2.5 0.5B via Ollama) can help fill missing identifiers, and the app falls back automatically if it is unavailable." },
  { q: "Can the AI change amounts or approve invoices?", a: "No. Models may only suggest identifying fields such as an invoice number, and only when that value literally appears in the document text. All financial values are extracted by rules or entered by people, validated deterministically, and approved by humans." },
  { q: "Does it verify GSTINs with the GST portal?", a: "It performs offline format and check-digit validation and compares the GSTIN with your supplier records. It does not query the GST Network, so it does not confirm registration status." },
  { q: "Which documents are supported?", a: "PDF (digital or scanned), JPG and PNG up to 10 MB and 10 pages by default. Both limits can be configured." },
  { q: "Are my documents sent to the cloud?", a: "Not by default. OCR runs locally with Tesseract. The optional Gemini provider is disabled unless an administrator explicitly enables cloud AI." },
  { q: "How are duplicates handled?", a: "Duplicates are stored and flagged with the matching invoice and the reasons. An accountant can mark a match as not a duplicate with a note, which is audited. Exact duplicates cannot be submitted for approval." },
  { q: "Can approvals have several levels?", a: "Yes. Admins configure up to five levels with amount thresholds. The default is a single manager approval. The same person cannot approve two levels or their own submission." },
  { q: "Is there a free plan?", a: "The software runs free on your own computer with SQLite. Hosted pricing shown on this site is illustrative for this portfolio MVP — no billing is connected." },
];
