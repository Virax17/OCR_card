from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image as PillowImage

from app.config import EXCEL_COLUMNS, EXCEL_HEADERS
from app.extraction.field_resolver import format_phone_for_display
from app.models import BusinessCardRecord

EXCEL_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def export_records(records: list[BusinessCardRecord], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "contacts"
    ws.append([EXCEL_HEADERS.get(column, column) for column in EXCEL_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F2937")

    image_dir = output.parent.parent / "images"

    for record in records:
        values = record.model_dump() if hasattr(record, "model_dump") else record.dict()
        values["business"] = record.business or record.company
        values["date"] = f"{record.date} {record.time}".strip()
        values["email1"] = record.email1 or record.email
        values["contact1"] = format_phone_for_display(
            record.contact1 or record.mobile_number or record.phone_primary,
            record.country_code,
        )
        values["contact2"] = format_phone_for_display(record.contact2 or record.phone_number, record.country_code)
        values["contact3"] = format_phone_for_display(record.contact3 or record.fax_number, record.country_code)
        values["low_confidence_fields"] = ", ".join(record.low_confidence_fields)
        values["reviewed_by_user"] = "Yes" if record.reviewed_by_user else "No"
        values["card"] = ""
        ws.append([values.get(column) for column in EXCEL_COLUMNS])
        row_index = ws.max_row
        ws.row_dimensions[row_index].height = 92
        _add_card_image(ws, image_dir / record.front_image_filename, row_index, "card") if record.front_image_filename else None
        fill = None
        if record.confidence_score == "Low":
            fill = PatternFill("solid", fgColor="FEE2E2")
        elif record.duplicate_flag != "No":
            fill = PatternFill("solid", fgColor="FEF9C3")
        if fill:
            for cell in ws[row_index]:
                cell.fill = fill

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col_idx, column in enumerate(EXCEL_COLUMNS, start=1):
        width = 38 if column == "card" else min(max(len(EXCEL_HEADERS.get(column, column)) + 2, 14), 42)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    wb.save(output)
    return output


def _add_card_image(ws, image_path: Path, row_index: int, column: str) -> None:
    if not image_path.exists() or column not in EXCEL_COLUMNS:
        return
    image_path = _excel_safe_image_path(image_path)
    col_idx = EXCEL_COLUMNS.index(column) + 1
    anchor = f"{get_column_letter(col_idx)}{row_index}"
    image = ExcelImage(str(image_path))
    image.width = 140
    image.height = 84
    ws.add_image(image, anchor)


def _excel_safe_image_path(image_path: Path) -> Path:
    if image_path.suffix.lower() in EXCEL_IMAGE_EXTENSIONS:
        return image_path
    cache_dir = image_path.parent / ".excel_image_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_path = cache_dir / f"{image_path.stem}.png"
    if safe_path.exists() and safe_path.stat().st_mtime >= image_path.stat().st_mtime:
        return safe_path
    with PillowImage.open(image_path) as source:
        image = source.convert("RGB")
        image.save(safe_path, "PNG")
    return safe_path
