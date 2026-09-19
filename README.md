# Hermes Invoice Extractor — Live Demo

> **Upload an invoice image. Get structured JSON data in seconds.**

Interactive Gradio web demo for the [Hermes Invoice Extractor](https://github.com/uspourmirza-boop/hermes-invoice-extract).

## Try It

**Hugging Face Spaces:** https://huggingface.co/spaces/uspourmirza-boop/hermes-invoice-extract

*Deploying now — coming soon*

## What It Does

This demo runs a production-grade OCR pipeline on your invoice or receipt image:

- Vendor name detection
- Date parsing (multi-format)
- Total, subtotal, tax extraction
- Invoice number identification
- Line item parsing
- Multi-currency support ($, €, £, ¥)

## Run Locally

```bash
git clone https://github.com/uspourmirza-boop/hermes-invoice-extract-demo.git
cd hermes-invoice-extract-demo
pip install -r requirements.txt
python app.py
```

## Technology

- **Tesseract OCR** — Industry-standard open-source OCR engine
- **Gradio** — Interactive web interface
- **Python + Pillow** — Image preprocessing and processing
- **MIT License** — Free and open source

## Part of the Hermes Economic Engine

This is **Stage 0** — free digital products that generate distribution and prove demand.

[Learn more](https://github.com/uspourmirza-boop/hermes-engine)
