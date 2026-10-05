"""QR code rendering. The QR encodes only the ticket's random token; all ticket data stays on the server."""
import base64
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_png(token):
    """PNG bytes of a QR code for the given ticket token."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(token)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(buffer, format='PNG')
    return buffer.getvalue()


def qr_data_uri(token):
    """QR code as a data: URI, ready for an <img src="..."> on the frontend."""
    return 'data:image/png;base64,' + base64.b64encode(qr_png(token)).decode()
