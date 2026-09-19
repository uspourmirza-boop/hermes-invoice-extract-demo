#!/usr/bin/env python3
"""
Hermes Invoice Extractor — Gradio Web Demo
==========================================

Live interactive demo deployed to Hugging Face Spaces.
Users upload an invoice image and get back structured data.
"""

import io
import json
import re
import tempfile
from pathlib import Path

import gradio as gr
from PIL import Image, ImageEnhance, ImageFilter

# Try to import pytesseract; provide graceful fallback if not available
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def preprocess(img: Image.Image) -> Image.Image:
    """Enhance image for OCR."""
    img = img.convert("L")
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


def extract_text(img: Image.Image) -> str:
    """Run Tesseract OCR on the image."""
    if not TESSERACT_AVAILABLE:
        return "[Tesseract not available in this environment. Install tesseract-ocr and pytesseract to enable extraction.]"
    processed = preprocess(img)
    custom_config = r"--oem 3 --psm 6"
    text = pytesseract.image_to_string(processed, config=custom_config)
    return text.strip()


def parse_invoice(text: str) -> dict:
    """Parse structured data from OCR text."""
    result = {
        "vendor": None,
        "date": None,
        "due_date": None,
        "total": None,
        "subtotal": None,
        "tax": None,
        "invoice_number": None,
        "currency": None,
        "line_items": [],
    }

    lines = text.split("\n")

    # Vendor: first non-empty line that looks like a company name
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) > 2:
            if not any(kw in stripped.lower() for kw in ["invoice", "receipt", "bill", "date", "total", "tax", "page"]):
                result["vendor"] = stripped
                break

    # Date patterns
    date_patterns = [
        (r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b", "%Y-%m-%d"),
        (r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b", "%m-%d-%Y"),
        (r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b", None),
        (r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b", None),
    ]

    # Look for date lines
    for line in lines:
        low = line.lower()
        is_due = "due" in low and "date" in low
        is_invoice_date = any(kw in low for kw in ["invoice date", "date:", "issued", "date of issue"])
        for pattern, _ in date_patterns:
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                date_str = m.group(1).strip()
                if is_due and not result["due_date"]:
                    result["due_date"] = date_str
                elif is_invoice_date and not result["date"]:
                    result["date"] = date_str
                elif not result["date"] and not is_due:
                    result["date"] = date_str

    # Amount patterns
    amount_pattern = r"[\$€£¥]?\s*[\d,]+\.?\d*"

    for line in lines:
        low = line.lower()

        # Total
        if any(kw in low for kw in ["total due", "amount due", "balance due", "total:", "total amount"]):
            m = re.search(r"[\$€£¥]\s*[\d,]+\.?\d{0,2}", line)
            if m and not result["total"]:
                raw = m.group(0)
                result["total"] = re.sub(r"[^\d.]", "", raw)
                curr_sym = re.search(r"[\$€£¥]", raw)
                if curr_sym:
                    result["currency"] = curr_sym.group(0)

        # Subtotal
        if "subtotal" in low or "sub-total" in low or "sub total" in low:
            m = re.search(r"[\$€£¥]?\s*[\d,]+\.?\d{0,2}", line)
            if m and not result["subtotal"]:
                raw = m.group(0)
                result["subtotal"] = re.sub(r"[^\d.]", "", raw)

        # Tax
        if any(kw in low for kw in ["tax", "vat", "gst"]):
            m = re.search(r"[\$€£¥]?\s*[\d,]+\.?\d{0,2}", line)
            if m and not result["tax"]:
                raw = m.group(0)
                result["tax"] = re.sub(r"[^\d.]", "", raw)

    # Total fallback: last dollar amount in the text
    if not result["total"]:
        all_amounts = re.findall(r"[\$€£¥]\s*[\d,]+\.?\d{0,2}", text)
        if all_amounts:
            result["total"] = re.sub(r"[^\d.]", "", all_amounts[-1])
            curr_sym = re.search(r"[\$€£¥]", all_amounts[-1])
            if curr_sym:
                result["currency"] = curr_sym.group(0)

    # Invoice number
    inv_patterns = [
        r"(?:invoice|inv|receipt|bill)\s*[#:]?\s*([A-Za-z0-9][\w\-/]*)",
        r"(?:no|number|ref)\s*[#:]?\s*([A-Za-z0-9][\w\-/]{2,})",
    ]
    for line in lines:
        for pattern in inv_patterns:
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if not any(kw in candidate.lower() for kw in ["page", "date", "total", "amount"]):
                    result["invoice_number"] = candidate
                    break
        if result["invoice_number"]:
            break

    # Line items
    for line in lines:
        m = re.search(r"^(.+?)\s+(\d+)\s+[\$€£¥]?\s*([\d,]+\.?\d{0,2})\s+[\$€£¥]?\s*([\d,]+\.?\d{0,2})", line)
        if m:
            result["line_items"].append({
                "description": m.group(1).strip(),
                "quantity": m.group(2),
                "unit_price": m.group(3).replace(",", ""),
                "amount": m.group(4).replace(",", ""),
            })

    return result


def process_image(img):
    """Main processing function for Gradio."""
    if img is None:
        return "Please upload an image.", ""

    text = extract_text(img)
    data = parse_invoice(text)

    summary_lines = []
    if data["vendor"]:
        summary_lines.append(f"Vendor: {data['vendor']}")
    if data["date"]:
        summary_lines.append(f"Date: {data['date']}")
    if data["due_date"]:
        summary_lines.append(f"Due Date: {data['due_date']}")
    if data["invoice_number"]:
        summary_lines.append(f"Invoice #: {data['invoice_number']}")
    if data["currency"] and data["total"]:
        summary_lines.append(f"Total: {data['currency']}{data['total']}")
    elif data["total"]:
        summary_lines.append(f"Total: {data['total']}")
    if data["subtotal"]:
        summary_lines.append(f"Subtotal: {data['subtotal']}")
    if data["tax"]:
        summary_lines.append(f"Tax: {data['tax']}")
    if data["line_items"]:
        summary_items = [f"  - {item['description']} ({item['quantity']}x {item['unit_price']} = {item['amount']})" for item in data["line_items"]]
        summary_lines.append("Line Items:")
        summary_lines.extend(summary_items)

    summary = "\n".join(summary_lines) if summary_lines else "No structured data found. The image may not contain a clear invoice/receipt, or quality may be too low."

    json_output = json.dumps(data, indent=2, ensure_ascii=False)

    return summary, json_output


# Build the Gradio interface
with gr.Blocks(
    title="Hermes Invoice Extractor",
    theme=gr.themes.Soft(),
    css="""
    .gradio-container {font-family: 'Inter', system-ui, sans-serif;}
    footer {display: none !important;}
    """,
) as demo:
    gr.Markdown("""
    # Hermes Invoice Extractor
    
    **Upload an invoice or receipt image. Get back structured data instantly.**
    
    This is a production-grade OCR pipeline. Extracts vendor, date, total, invoice number, and line items.
    """)

    with gr.Row():
        with gr.Column(scale=1):
            image_input = gr.Image(
                label="Invoice Image",
                type="pil",
                sources=["upload"],
                image_mode="RGB",
            )
            submit_btn = gr.Button("Extract Data", variant="primary")

        with gr.Column(scale=1):
            summary_output = gr.Textbox(
                label="Extracted Data",
                lines=12,
                show_copy_button=True,
            )
            json_output = gr.Code(
                label="JSON Output",
                language="json",
                lines=12,
            )

    gr.Markdown("""
    ---
    **How it works:** Tesseract OCR → image preprocessing → regex extraction → structured JSON.
    
    **Works best on:** clear printed text, high contrast, English. Handwritten or very low-quality images may have reduced accuracy.
    
    **Free and open source.** [View on GitHub](https://github.com/uspourmirza-boop/hermes-invoice-extract)
    """)

    submit_btn.click(
        fn=process_image,
        inputs=[image_input],
        outputs=[summary_output, json_output],
    )

    # Also process on image upload (auto-extract)
    image_input.upload(
        fn=process_image,
        inputs=[image_input],
        outputs=[summary_output, json_output],
    )

# Launch
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_name=7860)
