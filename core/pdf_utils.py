import io
from decimal import Decimal
from django.utils import timezone

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
)
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER


COMPANY_NAME = "JualGroup Ghana Ltd"
COMPANY_ADDRESS = "Industrial Area, Accra, Ghana"
COMPANY_PHONE = "+233 30 000 0000"
COMPANY_EMAIL = "info@jualgroup.com"
COMPANY_TAGLINE = "Industrial Automation & Engineering"


def _format_currency(value, currency='GHS'):
    try:
        num = Decimal(str(value or 0))
    except Exception:
        num = Decimal('0')
    return f"{currency} {num:,.2f}"


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(20 * mm, 15 * mm, COMPANY_NAME)
    canvas.drawRightString(
        A4[0] - 20 * mm, 15 * mm, f"Page {canvas.getPageNumber()}"
    )
    canvas.restoreState()


def _build_doc(buffer, title):
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        author=COMPANY_NAME,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )


def _company_header(story):
    styles = getSampleStyleSheet()

    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Normal'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=TA_LEFT,
    )
    tagline_style = ParagraphStyle(
        'Tagline',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.grey,
    )

    story.append(Paragraph(COMPANY_NAME, company_style))
    story.append(Paragraph(COMPANY_TAGLINE, tagline_style))
    story.append(Paragraph(COMPANY_ADDRESS, tagline_style))
    story.append(
        Paragraph(f"Tel: {COMPANY_PHONE} &nbsp;|&nbsp; {COMPANY_EMAIL}", tagline_style)
    )
    story.append(Spacer(1, 12 * mm))


def _doc_title(story, title, subtitle=None):
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    story.append(Paragraph(title, title_style))

    if subtitle:
        sub_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            alignment=TA_LEFT,
        )
        story.append(Paragraph(subtitle, sub_style))

    story.append(Spacer(1, 8 * mm))


def _info_table(rows, col_widths=None):
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
    )
    value_style = ParagraphStyle(
        'Value',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1e293b'),
    )

    data = [[
        Paragraph(label, label_style),
        Paragraph(str(value), value_style),
    ] for label, value in rows]

    t = Table(data, colWidths=col_widths or [60 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_invoice_pdf(invoice):
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Invoice {invoice.invoice_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"INVOICE {invoice.invoice_no}",
        f"Issue Date: {invoice.issue_date}  |  Due: {invoice.due_date or '—'}  |  Status: {invoice.get_status_display()}",
    )

    # Client info
    client_po = invoice.client_po
    quotation = getattr(client_po, 'quotation', None)
    client_name = client_po.client_po_number if client_po else '—'

    info_rows = [
        ("Billed To", f"Client PO Reference: {client_name}"),
        ("Internal Order No.", client_po.internal_order_no if client_po else '—'),
        ("Quotation Ref.", quotation.quote_no if quotation else '—'),
        ("Currency", invoice.currency),
    ]
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 8 * mm))

    # Line items
    line_data = [["#", "Description", "Amount (GHS)"]]
    line_data.append(["1", f"Invoice for {client_name}", _format_currency(invoice.amount, invoice.currency)])

    if invoice.tax_amount and invoice.tax_amount > 0:
        line_data.append(["2", "Tax / VAT", _format_currency(invoice.tax_amount, invoice.currency)])

    line_table = Table(line_data, colWidths=[12 * mm, 120 * mm, 38 * mm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 4 * mm))

    # Totals
    total_data = [
        ["", "Subtotal", _format_currency(invoice.amount, invoice.currency)],
        ["", "Tax", _format_currency(invoice.tax_amount, invoice.currency)],
        ["", "TOTAL DUE", _format_currency(invoice.total_amount, invoice.currency)],
    ]
    total_table = Table(total_data, colWidths=[100 * mm, 32 * mm, 38 * mm])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (1, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TEXTCOLOR', (1, 2), (-1, 2), colors.HexColor('#1e3a8a')),
        ('LINEABOVE', (1, 2), (-1, 2), 1, colors.HexColor('#1e3a8a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)

    # Footer note
    story.append(Spacer(1, 15 * mm))
    styles = getSampleStyleSheet()
    footer_note = ParagraphStyle(
        'FooterNote',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
    )
    story.append(Paragraph(
        "Thank you for your business. Please make payments to:<br/>"
        "Bank: Ecobank Ghana &nbsp;|&nbsp; Account: 0000000000000 &nbsp;|&nbsp; Branch: Accra Main",
        footer_note,
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer


def generate_quotation_pdf(quotation):
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Quotation {quotation.quote_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"QUOTATION {quotation.quote_no}",
        f"Date: {quotation.created_at.date()}  |  Valid Until: {quotation.valid_until or '—'}  |  Status: {quotation.get_status_display()}",
    )

    # Client info
    enquiry = quotation.enquiry
    info_rows = [
        ("Client", enquiry.client_name),
        ("Contact", enquiry.client_contact or '—'),
        ("Email", enquiry.client_email or '—'),
        ("Enquiry Ref.", enquiry.reference_no),
        ("Currency", quotation.currency),
    ]
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 8 * mm))

    # Line items
    line_data = [["#", "Description", "Qty", "Unit Price", "Total"]]
    for idx, item in enumerate(quotation.line_items.all(), start=1):
        line_data.append([
            str(idx),
            item.description,
            f"{item.quantity}",
            _format_currency(item.unit_price, quotation.currency),
            _format_currency(item.total, quotation.currency),
        ])

    if len(line_data) == 1:
        line_data.append([
            "1",
            f"Quotation for {enquiry.client_name}",
            "1",
            _format_currency(quotation.total_amount, quotation.currency),
            _format_currency(quotation.total_amount, quotation.currency),
        ])

    line_table = Table(line_data, colWidths=[10 * mm, 80 * mm, 15 * mm, 30 * mm, 35 * mm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 4 * mm))

    # Totals
    total_data = [
        ["", "TOTAL", _format_currency(quotation.total_amount, quotation.currency)],
    ]
    total_table = Table(total_data, colWidths=[95 * mm, 30 * mm, 35 * mm])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TEXTCOLOR', (1, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('LINEABOVE', (1, 0), (-1, 0), 1, colors.HexColor('#1e3a8a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(total_table)

    # Terms
    story.append(Spacer(1, 10 * mm))
    styles = getSampleStyleSheet()
    terms_style = ParagraphStyle(
        'Terms',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#1e293b'),
    )
    if quotation.terms:
        story.append(Paragraph("<b>Terms & Conditions</b>", terms_style))
        story.append(Paragraph(quotation.terms, terms_style))

    # Finance gate banner
    if quotation.status == 'PENDING_FINANCE':
        story.append(Spacer(1, 6 * mm))
        warn_style = ParagraphStyle(
            'Warn',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#92400e'),
        )
        story.append(Paragraph(
            "<b>⚠ PENDING FINANCE APPROVAL</b> — This quotation exceeds GHS 100,000 "
            "and requires Finance authorization before it can be submitted to the client.",
            warn_style,
        ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer

def generate_client_po_pdf(client_po):
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Client PO {client_po.internal_order_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"CLIENT PURCHASE ORDER",
        f"Order No: {client_po.internal_order_no}  |  Client PO: {client_po.client_po_number}  |  Date: {client_po.po_date}",
    )

    info_rows = [
        ("Internal Order No.", client_po.internal_order_no),
        ("Client PO Reference", client_po.client_po_number),
        ("PO Date", str(client_po.po_date)),
        ("Status", client_po.get_status_display()),
    ]
    if client_po.quotation:
        info_rows.append(("Quotation Ref.", client_po.quotation.quote_no))
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 8 * mm))

    # Line items
    line_data = [["#", "Description", "Qty", "Unit Price", "Total"]]
    items = client_po.items.all()
    if items:
        for idx, item in enumerate(items, start=1):
            line_data.append([
                str(idx),
                item.description,
                f"{item.quantity}",
                _format_currency(item.unit_price),
                _format_currency(item.total),
            ])
    else:
        line_data.append([
            "1",
            "Order value (no itemized breakdown)",
            "1",
            _format_currency(client_po.total_value),
            _format_currency(client_po.total_value),
        ])

    line_table = Table(line_data, colWidths=[10 * mm, 80 * mm, 15 * mm, 30 * mm, 35 * mm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 4 * mm))

    total_data = [
        ["", "TOTAL", _format_currency(client_po.total_value)],
    ]
    total_table = Table(total_data, colWidths=[95 * mm, 30 * mm, 35 * mm])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TEXTCOLOR', (1, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('LINEABOVE', (1, 0), (-1, 0), 1, colors.HexColor('#1e3a8a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(total_table)

    if client_po.user_requirements:
        story.append(Spacer(1, 10 * mm))
        styles = getSampleStyleSheet()
        note_style = ParagraphStyle(
            'Note',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#1e293b'),
        )
        story.append(Paragraph("<b>User Requirements</b>", note_style))
        story.append(Paragraph(client_po.user_requirements, note_style))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer



def generate_purchase_order_pdf(purchase_order):
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Purchase Order {purchase_order.po_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"PURCHASE ORDER {purchase_order.po_no}",
        f"Date: {purchase_order.created_at.date()}  |  Status: {purchase_order.get_status_display()}",
    )

    # Supplier info
    supplier = purchase_order.supplier
    info_rows = [
        ("Supplier", supplier.name),
        ("Contact", supplier.contact_person or '—'),
        ("Email", supplier.email or '—'),
        ("Phone", supplier.phone or '—'),
        ("Country", supplier.country or '—'),
    ]
    if purchase_order.sourcing_type:
        info_rows.append(
            ("Sourcing Type", purchase_order.get_sourcing_type_display())
        )
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 4 * mm))

    # Reference + delivery
    ref_rows = []
    if purchase_order.client_po:
        ref_rows.append(("Client PO Ref.", purchase_order.client_po.internal_order_no))
    if purchase_order.rfq:
        ref_rows.append(("RFQ Ref.", purchase_order.rfq.rfq_no))
    ref_rows.append(("Expected Delivery", str(purchase_order.expected_delivery or '—')))
    ref_rows.append(("Currency", purchase_order.currency))

    if purchase_order.order_confirmation_ref:
        ref_rows.append(("Supplier Confirmation Ref.", purchase_order.order_confirmation_ref))
        ref_rows.append(
            ("Confirmation Date", str(purchase_order.order_confirmation_date or '—'))
        )

    story.append(_info_table(ref_rows))
    story.append(Spacer(1, 8 * mm))

    # Line items
    line_data = [["#", "Description", "Qty", "Unit Price", "Total"]]
    items = purchase_order.items.all()
    if items:
        for idx, item in enumerate(items, start=1):
            line_data.append([
                str(idx),
                item.description,
                f"{item.quantity}",
                _format_currency(item.unit_price, purchase_order.currency),
                _format_currency(item.total, purchase_order.currency),
            ])
    else:
        line_data.append([
            "1",
            "Purchase order value (no itemized breakdown)",
            "1",
            _format_currency(purchase_order.total_cost, purchase_order.currency),
            _format_currency(purchase_order.total_cost, purchase_order.currency),
        ])

    line_table = Table(line_data, colWidths=[10 * mm, 80 * mm, 15 * mm, 30 * mm, 35 * mm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 4 * mm))

    # Totals
    total_rows = [["", "Goods Total", _format_currency(purchase_order.total_cost, purchase_order.currency)]]
    if purchase_order.freight_cost and purchase_order.freight_cost > 0:
        total_rows.append(
            ["", "Freight / Shipping", _format_currency(purchase_order.freight_cost, purchase_order.currency)]
        )
        grand_total = purchase_order.total_cost + purchase_order.freight_cost
        total_rows.append(
            ["", "GRAND TOTAL", _format_currency(grand_total, purchase_order.currency)]
        )
    else:
        total_rows.append(
            ["", "GRAND TOTAL", _format_currency(purchase_order.total_cost, purchase_order.currency)]
        )

    total_table = Table(total_rows, colWidths=[95 * mm, 30 * mm, 35 * mm])
    total_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (1, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, -1), (-1, -1), colors.HexColor('#1e3a8a')),
        ('LINEABOVE', (1, -1), (-1, -1), 1, colors.HexColor('#1e3a8a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)

    # Shipping & logistics
    if purchase_order.carrier or purchase_order.tracking_number or purchase_order.shipping_notes:
        story.append(Spacer(1, 10 * mm))
        styles = getSampleStyleSheet()
        ship_heading = ParagraphStyle(
            'ShipHead',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=colors.HexColor('#1e3a8a'),
            spaceAfter=4,
        )
        story.append(Paragraph("Shipping & Logistics", ship_heading))

        ship_rows = []
        if purchase_order.carrier:
            ship_rows.append(("Carrier", purchase_order.get_carrier_display() or purchase_order.carrier))
        if purchase_order.carrier_name:
            ship_rows.append(("Forwarder", purchase_order.carrier_name))
        if purchase_order.tracking_number:
            ship_rows.append(("Tracking #", purchase_order.tracking_number))
        if ship_rows:
            story.append(_info_table(ship_rows))

        if purchase_order.shipping_notes:
            ship_note = ParagraphStyle(
                'ShipNote',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#334155'),
            )
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(purchase_order.shipping_notes, ship_note))

    # General notes
    if purchase_order.notes:
        story.append(Spacer(1, 10 * mm))
        styles = getSampleStyleSheet()
        note_style = ParagraphStyle(
            'Note',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#1e293b'),
        )
        story.append(Paragraph("<b>Notes</b>", note_style))
        story.append(Paragraph(purchase_order.notes, note_style))

    # Footer
    story.append(Spacer(1, 12 * mm))
    styles = getSampleStyleSheet()
    footer_style = ParagraphStyle(
        'FooterNote',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    story.append(Paragraph(
        "This is a computer-generated Purchase Order. Please quote the PO number on all correspondence.",
        footer_style,
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer


def generate_soa_pdf(soa):
    from finance.models import Invoice, Payment

    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"SOA {soa.soa_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"STATEMENT OF ACCOUNT",
        f"{soa.soa_no}  |  {soa.client_name}  |  {soa.period_start} to {soa.period_end}",
    )

    info_rows = [
        ("Client", soa.client_name),
        ("Statement No.", soa.soa_no),
        ("Period", f"{soa.period_start} to {soa.period_end}"),
        ("Currency", soa.currency),
        ("Status", soa.status),
    ]
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 8 * mm))

    # Fetch transactions
    invoices = Invoice.objects.filter(
        client_po__quotation__enquiry__client_name__iexact=soa.client_name,
        issue_date__gte=soa.period_start,
        issue_date__lte=soa.period_end,
    ).order_by('issue_date')

    payments = Payment.objects.filter(
        invoice__client_po__quotation__enquiry__client_name__iexact=soa.client_name,
        payment_date__gte=soa.period_start,
        payment_date__lte=soa.period_end,
    ).select_related('invoice').order_by('payment_date')

    # Build transactions list
    txns = []
    for inv in invoices:
        txns.append({
            'date': inv.issue_date,
            'ref': inv.invoice_no,
            'description': f"Invoice — {inv.invoice_no}",
            'debit': inv.total_amount,
            'credit': 0,
        })
    for pay in payments:
        txns.append({
            'date': pay.payment_date,
            'ref': pay.receipt_no,
            'description': f"Payment received — {pay.payment_method} ({pay.invoice.invoice_no})",
            'debit': 0,
            'credit': pay.amount,
        })
    txns.sort(key=lambda x: x['date'])

    # Opening balance row
    line_data = [["Date", "Reference", "Description", "Debit", "Credit", "Balance"]]
    running = soa.opening_balance
    line_data.append([
        str(soa.period_start),
        "—",
        "Opening Balance",
        "—",
        "—",
        _format_currency(running, soa.currency),
    ])

    for t in txns:
        running = running + t['debit'] - t['credit']
        line_data.append([
            str(t['date']),
            t['ref'],
            t['description'][:60],
            _format_currency(t['debit'], soa.currency) if t['debit'] else '—',
            _format_currency(t['credit'], soa.currency) if t['credit'] else '—',
            _format_currency(running, soa.currency),
        ])

    line_table = Table(
        line_data,
        colWidths=[22 * mm, 22 * mm, 60 * mm, 22 * mm, 22 * mm, 22 * mm],
    )
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 5 * mm))

    # Summary
    summary_data = [
        ["Opening Balance", _format_currency(soa.opening_balance, soa.currency)],
        ["Invoices Issued (Debits)", _format_currency(soa.total_debits, soa.currency)],
        ["Payments Received (Credits)", _format_currency(soa.total_credits, soa.currency)],
        ["CLOSING BALANCE", _format_currency(soa.closing_balance, soa.currency)],
    ]
    summary_table = Table(summary_data, colWidths=[120 * mm, 45 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#1e3a8a')),
        ('LINEABOVE', (0, 3), (-1, 3), 1, colors.HexColor('#1e3a8a')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    story.append(Spacer(1, 15 * mm))
    styles = getSampleStyleSheet()
    footer_note = ParagraphStyle(
        'FooterNote',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
    )
    story.append(Paragraph(
        "Please note: If payment has been made recently, kindly disregard this statement.<br/>"
        "For any queries, contact: accounts@jualgroup.com",
        footer_note,
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer



def generate_requisition_pdf(requisition):
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Requisition {requisition.req_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"REQUISITION — {requisition.get_requisition_type_display().upper()}",
        f"Ref: {requisition.req_no}  |  Status: {requisition.get_status_display()}",
    )

    info_rows = [
        ("Type", requisition.get_requisition_type_display()),
    ]
    if requisition.source_department:
        info_rows.append(("Department", requisition.get_source_department_display()))
    if requisition.client_po:
        info_rows.append(("Client PO", requisition.client_po.internal_order_no))
    if requisition.requesting_branch:
        info_rows.append(("From Branch", requisition.requesting_branch.name))
    if requisition.target_branch:
        info_rows.append(("To Branch", requisition.target_branch.name))
    if requisition.requested_by:
        info_rows.append(("Requested By", requisition.requested_by.get_full_name() or requisition.requested_by.username))
    info_rows.append(("Requested On", str(requisition.created_at.date())))
    if requisition.waybill_no:
        info_rows.append(("Waybill No.", requisition.waybill_no))
    if requisition.carrier:
        info_rows.append(("Carrier", requisition.carrier))

    story.append(_info_table(info_rows))
    story.append(Spacer(1, 8 * mm))

    # Line items
    line_data = [["#", "Description", "UoM", "Requested", "Approved", "Issued"]]
    for idx, item in enumerate(requisition.items.all(), start=1):
        line_data.append([
            str(idx),
            item.description,
            item.uom,
            str(item.quantity_requested),
            str(item.quantity_approved),
            str(item.quantity_issued),
        ])

    line_table = Table(line_data, colWidths=[10 * mm, 70 * mm, 15 * mm, 25 * mm, 25 * mm, 25 * mm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)

    if requisition.notes:
        story.append(Spacer(1, 10 * mm))
        styles = getSampleStyleSheet()
        note_style = ParagraphStyle(
            'Note', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#1e293b'),
        )
        story.append(Paragraph("<b>Notes</b>", note_style))
        story.append(Paragraph(requisition.notes, note_style))

    # Signature block
    story.append(Spacer(1, 15 * mm))
    sig_data = [
        ["_______________________", "_______________________"],
        ["Prepared By", "Received By"],
    ]
    sig_table = Table(sig_data, colWidths=[80 * mm, 80 * mm])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer



def generate_stock_transfer_pdf(transfer):
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Transfer {transfer.transfer_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"STOCK TRANSFER — {transfer.get_transfer_type_display().upper()}",
        f"Ref: {transfer.transfer_no}  |  Waybill: {transfer.waybill_no or '—'}  |  Status: {transfer.get_status_display()}",
    )

    info_rows = [
        ("From Branch", transfer.from_branch.name),
        ("To Branch", transfer.to_branch.name),
        ("Transfer Type", transfer.get_transfer_type_display()),
        ("Requested By", transfer.requested_by.get_full_name() if transfer.requested_by else '—'),
        ("Requested On", str(transfer.created_at.date())),
    ]
    if transfer.approved_by:
        info_rows.append(("Approved By", transfer.approved_by.get_full_name()))
    if transfer.dispatched_at:
        info_rows.append(("Dispatched On", str(transfer.dispatched_at.date())))
    if transfer.received_at:
        info_rows.append(("Received On", str(transfer.received_at.date())))

    story.append(_info_table(info_rows))
    story.append(Spacer(1, 8 * mm))

    # Line items
    line_data = [["#", "Description", "UoM", "Requested", "Approved", "Dispatched", "Received"]]
    for idx, item in enumerate(transfer.items.all(), start=1):
        line_data.append([
            str(idx),
            item.description,
            item.uom,
            str(item.quantity_requested),
            str(item.quantity_approved),
            str(item.quantity_dispatched),
            str(item.quantity_received),
        ])

    line_table = Table(
        line_data,
        colWidths=[8 * mm, 60 * mm, 12 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm],
    )
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)

    if transfer.purpose:
        story.append(Spacer(1, 8 * mm))
        styles = getSampleStyleSheet()
        note_style = ParagraphStyle(
            'Note', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#1e293b'),
        )
        story.append(Paragraph("<b>Purpose</b>", note_style))
        story.append(Paragraph(transfer.purpose, note_style))

    # Signature block
    story.append(Spacer(1, 15 * mm))
    sig_data = [
        ["_______________________", "_______________________", "_______________________"],
        ["Dispatched By", "Carried By", "Received By"],
    ]
    sig_table = Table(sig_data, colWidths=[55 * mm, 55 * mm, 55 * mm])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer



# =========================================================================
# PHASE 3 — Inventory PDFs (stock receipt, stock report)
# =========================================================================

def generate_stock_receipt_pdf(movement):
    """Receipt / issue slip for a single StockMovement."""
    buffer = io.BytesIO()
    doc = _build_doc(buffer, f"Stock Movement {movement.movement_no}")
    story = []

    _company_header(story)
    _doc_title(
        story,
        f"STOCK {movement.get_direction_display().upper()}",
        f"Ref: {movement.movement_no}  |  {movement.get_movement_type_display()}  |  {movement.performed_at:%d %b %Y %H:%M}",
    )

    # Item + branch
    info_rows = [
        ("Item", f"{movement.item.part_number} — {movement.item.description}"),
        ("UoM", movement.item.uom),
        ("Branch", movement.branch.name),
        ("Direction", movement.get_direction_display()),
        ("Type", movement.get_movement_type_display()),
        ("Quantity", f"{movement.quantity} {movement.item.uom}"),
        ("Unit Cost", _format_currency(movement.unit_cost)),
        ("Total Cost", _format_currency(movement.total_cost)),
    ]
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 6 * mm))

    # Counterparty
    cp_rows = [("Counterparty", movement.get_counterparty_type_display())]
    if movement.supplier:
        cp_rows.append(("Supplier", movement.supplier.name))
    if movement.client_po:
        cp_rows.append(("Client PO", movement.client_po.internal_order_no))
    if movement.purchase_order:
        cp_rows.append(("Purchase Order", movement.purchase_order.po_no))
    if movement.grn:
        cp_rows.append(("GRN", movement.grn.grn_no))
    if movement.reference:
        cp_rows.append(("External Reference", movement.reference))
    if movement.performed_by:
        cp_rows.append((
            "Performed By",
            movement.performed_by.get_full_name() or movement.performed_by.username,
        ))
    story.append(_info_table(cp_rows))

    # Reason / notes
    if movement.reason or movement.notes:
        story.append(Spacer(1, 8 * mm))
        styles = getSampleStyleSheet()
        note_style = ParagraphStyle(
            'Note', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#1e293b'),
        )
        if movement.reason:
            story.append(Paragraph("<b>Reason</b>", note_style))
            story.append(Paragraph(movement.reason, note_style))
        if movement.notes:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("<b>Notes</b>", note_style))
            story.append(Paragraph(movement.notes, note_style))

    # Signature block
    story.append(Spacer(1, 20 * mm))
    sig_data = [
        ["_______________________", "_______________________", "_______________________"],
        ["Issued By", "Checked By", "Received By"],
    ]
    sig_table = Table(sig_data, colWidths=[55 * mm, 55 * mm, 55 * mm])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer


def generate_stock_report_pdf(branch=None, category=None, include_values=True):
    """Inventory report — on-hand, received, issued, returned, rejected, total value."""
    from procurement.models import InventoryItem, BranchStock

    buffer = io.BytesIO()
    title = "Inventory Stock Report"
    doc = _build_doc(buffer, title)
    story = []

    _company_header(story)

    subtitle_parts = [f"Generated: {timezone.now():%d %b %Y %H:%M}"]
    if branch:
        subtitle_parts.append(f"Branch: {branch.name}")
    if category:
        subtitle_parts.append(f"Category: {category}")

    _doc_title(story, title.upper(), "  |  ".join(subtitle_parts))

    # Pick the queryset
    if branch:
        qs = (
            BranchStock.objects
            .filter(branch=branch)
            .select_related('item', 'branch')
            .order_by('item__part_number')
        )
        rows_source = [('branch_stock', bs) for bs in qs]
    else:
        qs = InventoryItem.objects.filter(is_active=True).order_by('part_number')
        if category:
            qs = qs.filter(category=category)
        rows_source = [('item', it) for it in qs]

    # Build table
    header = ["#", "Part No.", "Description", "UoM", "On Hand"]
    if include_values:
        header += ["Unit Cost", "Total Value"]
    if branch:
        header += ["Received", "Issued", "Returned", "Rejected"]

    line_data = [header]
    total_value = Decimal('0')
    total_units = Decimal('0')

    for idx, (kind, obj) in enumerate(rows_source, start=1):
        if kind == 'branch_stock':
            it = obj.item
            on_hand = obj.quantity_on_hand or 0
            row = [
                str(idx),
                it.part_number,
                it.description[:40],
                it.uom,
                f"{on_hand}",
            ]
            if include_values:
                unit_cost = it.unit_cost or 0
                val = (on_hand or 0) * (unit_cost or 0)
                total_value += Decimal(str(val))
                row += [
                    _format_currency(unit_cost),
                    _format_currency(val),
                ]
            row += [
                f"{obj.qty_received or 0}",
                f"{obj.qty_issued or 0}",
                f"{obj.qty_returned or 0}",
                f"{obj.qty_rejected or 0}",
            ]
        else:
            on_hand = obj.quantity_on_hand or 0
            row = [
                str(idx),
                obj.part_number,
                obj.description[:40],
                obj.uom,
                f"{on_hand}",
            ]
            if include_values:
                unit_cost = obj.unit_cost or 0
                val = (on_hand or 0) * (unit_cost or 0)
                total_value += Decimal(str(val))
                row += [
                    _format_currency(unit_cost),
                    _format_currency(val),
                ]
        total_units += Decimal(str(on_hand))
        line_data.append(row)

    # Column widths
    if branch:
        col_widths = [8 * mm, 28 * mm, 55 * mm, 12 * mm, 18 * mm]
        if include_values:
            col_widths += [22 * mm, 25 * mm]
        col_widths += [18 * mm, 18 * mm, 18 * mm, 18 * mm]
    else:
        col_widths = [8 * mm, 30 * mm, 65 * mm, 14 * mm, 20 * mm]
        if include_values:
            col_widths += [25 * mm, 28 * mm]

    # Fit into A4 printable width (~170mm). Scale down if needed.
    total_w = sum(col_widths)
    max_w = A4[0] - 40 * mm
    if total_w > max_w:
        scale = float(max_w) / float(total_w)
        col_widths = [w * scale for w in col_widths]

    line_table = Table(line_data, colWidths=col_widths, repeatRows=1)
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(line_table)

    # Totals
    story.append(Spacer(1, 5 * mm))
    totals_rows = [["Total Items", str(len(rows_source)), "Total Units", f"{total_units:,.2f}"]]
    if include_values:
        totals_rows.append(["", "", "Total Value", _format_currency(total_value)])
    totals_table = Table(totals_rows, colWidths=[35 * mm, 30 * mm, 35 * mm, 50 * mm])
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#1e3a8a')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(totals_table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer