"""Writes a small text PDF (Helvetica, one text layer per page) with the
standard library, so the selftest needs no PDF writer. The deck belongs to the
fictional brand of the fixture site, Fixturely."""

from pathlib import Path
from typing import List

DECK = [
    ["Fixturely", "Invoices that chase themselves", "For freelance designers and small studios"],
    ["The problem", "Freelancers spend Friday afternoons chasing late invoices", "Reminders feel awkward, so they wait"],
    ["Traction", "1 240 freelancers on the waitlist in September 2026", "38 studios sent 2 900 invoices during the pilot"],
    ["What a pilot studio said", "We get paid in a week now.", "Lena Park, Parkline Design"],
]


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(path: Path, pages: List[List[str]] = DECK) -> Path:
    objects: List[bytes] = []
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, lines in enumerate(pages):
        text = "BT /F1 20 Tf 72 720 Td 30 TL " + " T* ".join(f"({_escape(x)}) Tj" for x in lines) + " ET"
        stream = text.encode("latin-1")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {5 + 2 * i} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path
