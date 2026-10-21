"""What an archived capture actually is: the real document, the library's
anti-bot challenge, its maintenance page, or something else."""
import re

def classify(body: bytes, mime: str = "") -> str:
    head = body[:4000]
    if body[:5] == b"%PDF-":
        return "pdf"
    if b"bobcmn" in head or b"TSPD" in head:
        return "challenge"
    if b"em manuten&#231;&#227;o" in body or "em manutenção".encode() in body:
        return "maintenance"
    if re.search(rb'documentFirstHeading|parent-fieldname-text|id="content-core"|class="documentDescription"', body):
        return "page"
    if len(body) < 2000:
        return "tiny"
    return "other-html"
