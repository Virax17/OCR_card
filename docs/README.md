# Business Card LLM Scanner Docs

Status: Active implementation notes  
Last updated: 2026-07-02  
Owner: Tritorc OCR project

## Purpose

This folder is the Obsidian-friendly planning and implementation space for the business card scanner.

The current product goal is to scan one-sided or two-sided business cards, extract contact details accurately with Google Vision OCR plus Gemini text sorting, store the result in SQLite, and export event-wise Excel files with card images for verification.

## Current Planning Docs

- [[01-paddleocr-business-card-scanner-hld]]
- [[02-llm-minimized-extraction-design]]
- [[03-paddleocr-business-card-scanner-lld]]
- [[04-implementation-plan-review]]
- [[05-decision-log]]
- [[06-database-plan]]
- [[07-sqlite-setup]]
- [[08-gemini-mcp-usage]]
- [[09-ocr-ensemble-plan]]
- [[10-business-card-sample-learning]]
- [[11-google-vision-ocr-runtime]]
- [[12-deployment-security-plan]]

## Runtime Summary

```text
Google Vision OCR -> deterministic candidates -> Gemini text sorter -> SQLite -> Excel
```

Gemini is used once per card in the normal upload flow. Google Vision OCR is counted once per uploaded image side.

## External References

- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Google Vision OCR docs: https://cloud.google.com/vision/docs/ocr
- PaddleOCR notes used for planning:
  - PaddleOCR supports image and document OCR with structured JSON/Markdown-style outputs.
  - PaddleOCR positions PP-OCR as scene OCR for text spotting and recognition.
  - Recent PaddleOCR releases include multilingual OCR, document parsing, deployment, and CPU/GPU acceleration options.
