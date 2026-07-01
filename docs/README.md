# Business Card LLM Scanner Docs

Status: Review draft  
Last updated: 2026-07-01  
Owner: Tritorc OCR project

## Purpose

This folder is the Obsidian-friendly planning space for the business card scanner.

The current product goal is to scan one-sided or two-sided business cards, extract contact details accurately with one Gemini Vision call per card, and store the result in an Excel-compatible tabular structure.

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

## Review Rule

No code implementation should start until the implementation plan is reviewed and approved.

## External References

- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR notes used for planning:
  - PaddleOCR supports image and document OCR with structured JSON/Markdown-style outputs.
  - PaddleOCR positions PP-OCR as scene OCR for text spotting and recognition.
  - Recent PaddleOCR releases include multilingual OCR, document parsing, deployment, and CPU/GPU acceleration options.
