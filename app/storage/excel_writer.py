from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config import EXCEL_COLUMNS, EXCEL_HEADERS
from app.models import BusinessCardRecord


def export_records(records: list[BusinessCardRecord], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append([EXCEL_HEADERS.get(column, column) for column in EXCEL_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F2937")

    image_dir = output.parent.parent / "images"

    for record in records:
        values = record.model_dump() if hasattr(record, "model_dump") else record.dict()
        values["business"] = record.business or record.company
        values["low_confidence_fields"] = ", ".join(record.low_confidence_fields)
        values["reviewed_by_user"] = "Yes" if record.reviewed_by_user else "No"
        values["front_image"] = ""
        values["back_image"] = ""
        ws.append([values.get(column) for column in EXCEL_COLUMNS])
        row_index = ws.max_row
        ws.row_dimensions[row_index].height = 92
        _add_card_image(ws, image_dir / record.front_image_filename, row_index, "front_image") if record.front_image_filename else None
        _add_card_image(ws, image_dir / record.back_image_filename, row_index, "back_image") if record.back_image_filename else None
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
        width = 20 if column in {"front_image", "back_image"} else min(max(len(column) + 2, 14), 34)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    wb.save(output)
    return output


def _add_card_image(ws, image_path: Path, row_index: int, column: str) -> None:
    if not image_path.exists() or column not in EXCEL_COLUMNS:
        return
    col_idx = EXCEL_COLUMNS.index(column) + 1
    anchor = f"{get_column_letter(col_idx)}{row_index}"
    image = ExcelImage(str(image_path))
    image.width = 140
    image.height = 84
    ws.add_image(image, anchor)
