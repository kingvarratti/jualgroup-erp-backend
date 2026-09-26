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
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 4 * mm))

    # Client PO reference
    if purchase_order.client_po:
        story.append(Spacer(1, 2 * mm))
        ref_rows = [
            ("Client PO Ref.", purchase_order.client_po.internal_order_no),
            ("Expected Delivery", str(purchase_order.expected_delivery or '—')),
            ("Currency", purchase_order.currency),
        ]
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

    # Total
    total_data = [
        ["", "TOTAL", _format_currency(purchase_order.total_cost, purchase_order.currency)],
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