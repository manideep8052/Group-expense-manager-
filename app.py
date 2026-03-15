from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from functools import wraps
from database import db, init_db
from models import Expense
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import pagesizes
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///group_expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PDF_FOLDER'] = 'pdf_exports'

# Create PDF folder if it doesn't exist
if not os.path.exists('pdf_exports'):
    os.makedirs('pdf_exports')

db.init_app(app)

# Simple hardcoded credentials (change these in production)
VALID_USERNAME = "admin"
VALID_PASSWORD = "password123"

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login first')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Members list
members = [
    "Jayachandra",
    "Abhiram",
    "Manideep",
    "Abhi satya ram",
    "Rajesh",
    "JAMAR"
]

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            session['login_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    expenses = Expense.query.order_by(Expense.date.desc(), Expense.time.desc()).all()
    total_amount = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    
    # Calculate individual totals
    individual_totals = {}
    for member in members:
        total = db.session.query(db.func.sum(Expense.amount)).filter_by(person=member).scalar() or 0
        individual_totals[member] = total
    
    # Get recent expenses (last 10)
    recent_expenses = expenses[:10] if expenses else []
    
    # Calculate statistics
    total_members = len(members)
    avg_per_person = total_amount / total_members if total_members > 0 else 0
    
    # Find highest spender
    highest_spender = None
    highest_amount = 0
    for member, amount in individual_totals.items():
        if amount > highest_amount:
            highest_amount = amount
            highest_spender = member
    
    return render_template('dashboard.html', 
                         expenses=recent_expenses,
                         total_amount=total_amount,
                         individual_totals=individual_totals,
                         members=members,
                         avg_per_person=avg_per_person,
                         highest_spender=highest_spender,
                         highest_amount=highest_amount,
                         total_transactions=len(expenses))

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        person = request.form.get('person')
        amount = float(request.form.get('amount'))
        purpose = request.form.get('purpose')
        
        now = datetime.now()
        date = now.strftime("%d-%m-%Y")
        time = now.strftime("%I:%M:%S %p")
        
        expense = Expense(
            date=date,
            time=time,
            person=person,
            amount=amount,
            purpose=purpose
        )
        
        db.session.add(expense)
        db.session.commit()
        
        flash(f'Expense of ₹{amount} added for {person}', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_expense.html', members=members)

@app.route('/entries')
@login_required
def all_entries():
    # Get filter parameters
    person_filter = request.args.get('person', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Expense.query
    
    if person_filter:
        query = query.filter_by(person=person_filter)
    if date_from:
        query = query.filter(Expense.date >= date_from)
    if date_to:
        query = query.filter(Expense.date <= date_to)
    
    expenses = query.order_by(Expense.date.desc(), Expense.time.desc()).all()
    
    return render_template('entries.html', 
                         expenses=expenses, 
                         members=members,
                         person_filter=person_filter,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/edit_entry/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    expense = Expense.query.get_or_404(entry_id)
    
    if request.method == 'POST':
        old_amount = expense.amount
        expense.person = request.form.get('person')
        expense.amount = float(request.form.get('amount'))
        expense.purpose = request.form.get('purpose')
        
        db.session.commit()
        flash(f'Expense updated from ₹{old_amount} to ₹{expense.amount}', 'success')
        return redirect(url_for('all_entries'))
    
    return render_template('edit_entry.html', expense=expense, members=members)

@app.route('/delete_entry/<int:entry_id>')
@login_required
def delete_entry(entry_id):
    expense = Expense.query.get_or_404(entry_id)
    amount = expense.amount
    person = expense.person
    
    db.session.delete(expense)
    db.session.commit()
    
    flash(f'Expense of ₹{amount} for {person} deleted', 'info')
    return redirect(url_for('all_entries'))

@app.route('/individual/<person>')
@login_required
def individual_entries(person):
    expenses = Expense.query.filter_by(person=person).order_by(Expense.date.desc(), Expense.time.desc()).all()
    total = sum(exp.amount for exp in expenses)
    
    # Calculate monthly totals for the graph
    monthly_totals = {}
    for exp in expenses:
        month = exp.date[:7]  # Get YYYY-MM from date
        monthly_totals[month] = monthly_totals.get(month, 0) + exp.amount
    
    return render_template('individual_entries.html', 
                         person=person, 
                         expenses=expenses, 
                         total=total,
                         monthly_totals=monthly_totals)

@app.route('/totals')
@login_required
def totals():
    individual_totals = {}
    for member in members:
        total = db.session.query(db.func.sum(Expense.amount)).filter_by(person=member).scalar() or 0
        individual_totals[member] = total
    
    group_total = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    total_transactions = Expense.query.count()
    
    # Calculate percentages
    for member in individual_totals:
        individual_totals[member] = {
            'amount': individual_totals[member],
            'percentage': (individual_totals[member] / group_total * 100) if group_total > 0 else 0
        }
    
    return render_template('totals.html', 
                         individual_totals=individual_totals,
                         group_total=group_total,
                         members=members,
                         total_transactions=total_transactions)

@app.route('/export_all_pdf')
@login_required
def export_all_pdf():
    expenses = Expense.query.order_by(Expense.date, Expense.time).all()
    
    if not expenses:
        flash('No data to export', 'warning')
        return redirect(url_for('dashboard'))
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f'Group_Expense_Report_{timestamp}.pdf'
    pdf_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)
    
    # Create PDF
    doc = SimpleDocTemplate(pdf_path, pagesize=pagesizes.A4, 
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    elements.append(Paragraph("GROUP EXPENSE REPORT", title_style))
    
    # Date and Time
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.gray,
        alignment=TA_RIGHT
    )
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}", date_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Summary Section
    total_amount = sum(exp.amount for exp in expenses)
    avg_amount = total_amount / len(expenses) if expenses else 0
    
    summary_data = [
        ['Total Expenses', f'₹{total_amount:,.2f}'],
        ['Number of Transactions', str(len(expenses))],
        ['Average per Transaction', f'₹{avg_amount:,.2f}']
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ('GRID', (0,0), (-1,-1), 1, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Individual Totals
    individual_totals = {}
    for member in members:
        total = sum(exp.amount for exp in expenses if exp.person == member)
        if total > 0:
            individual_totals[member] = total
    
    if individual_totals:
        elements.append(Paragraph("<b>INDIVIDUAL TOTALS</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.1 * inch))
        
        indiv_data = [['Member', 'Total Amount', 'Percentage']]
        for member, total in individual_totals.items():
            percentage = (total / total_amount * 100) if total_amount > 0 else 0
            indiv_data.append([member, f'₹{total:,.2f}', f'{percentage:.1f}%'])
        
        indiv_table = Table(indiv_data, colWidths=[150, 150, 100])
        indiv_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,1), (-1,-1), 9),
        ]))
        
        elements.append(indiv_table)
        elements.append(Spacer(1, 0.3 * inch))
    
    # Main Expense Table
    elements.append(Paragraph("<b>DETAILED TRANSACTIONS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1 * inch))
    
    # Table Header
    data = [["S.No", "Date", "Time", "Member", "Amount (₹)", "Purpose"]]
    
    # Add data rows
    for idx, exp in enumerate(expenses, 1):
        data.append([
            str(idx),
            exp.date,
            exp.time,
            exp.person,
            f'₹{exp.amount:,.2f}',
            exp.purpose[:40] + '...' if len(exp.purpose) > 40 else exp.purpose
        ])
    
    # Add total row
    data.append(["", "", "", "TOTAL", f'₹{total_amount:,.2f}', ""])
    
    # Create table
    table = Table(data, colWidths=[40, 70, 70, 100, 80, 150])
    
    # Table style
    style = TableStyle([
        # Header style
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        
        # Grid style
        ('GRID', (0,0), (-1,-2), 1, colors.lightgrey),
        ('GRID', (0,-1), (-1,-1), 2, colors.black),
        
        # Total row style
        ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 10),
        
        # Cell padding
        ('PADDING', (0,0), (-1,-1), 6),
        
        # Alignment
        ('ALIGN', (0,1), (0,-1), 'CENTER'),
        ('ALIGN', (1,1), (2,-1), 'CENTER'),
        ('ALIGN', (4,1), (4,-1), 'RIGHT'),
        ('ALIGN', (5,1), (5,-1), 'LEFT'),
    ])
    
    # Alternate row colors
    for i in range(1, len(data)-1):
        if i % 2 == 0:
            style.add('BACKGROUND', (0,i), (-1,i), colors.whitesmoke)
    
    table.setStyle(style)
    elements.append(table)
    
    # Footer
    elements.append(Spacer(1, 0.3 * inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("This is a system generated report", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    flash(f'PDF exported successfully: {pdf_filename}', 'success')
    return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)

@app.route('/export_individual_pdf/<person>')
@login_required
def export_individual_pdf(person):
    expenses = Expense.query.filter_by(person=person).order_by(Expense.date, Expense.time).all()
    
    if not expenses:
        flash(f'No data found for {person}', 'warning')
        return redirect(url_for('individual_entries', person=person))
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f'{person}_Report_{timestamp}.pdf'
    pdf_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)
    
    # Create PDF
    doc = SimpleDocTemplate(pdf_path, pagesize=pagesizes.A4,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#27ae60'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    elements.append(Paragraph(f"{person.upper()} - EXPENSE REPORT", title_style))
    
    # Date and Time
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.gray,
        alignment=TA_RIGHT
    )
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}", date_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Summary
    total_amount = sum(exp.amount for exp in expenses)
    
    summary_data = [
        ['Member Name', person],
        ['Total Expenses', f'₹{total_amount:,.2f}'],
        ['Number of Transactions', str(len(expenses))],
        ['Average per Transaction', f'₹{total_amount/len(expenses):,.2f}' if expenses else '₹0']
    ]
    
    summary_table = Table(summary_data, colWidths=[150, 250])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('GRID', (0,0), (-1,-1), 1, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Transactions Table
    elements.append(Paragraph("<b>TRANSACTION DETAILS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1 * inch))
    
    data = [["S.No", "Date", "Time", "Amount (₹)", "Purpose"]]
    
    for idx, exp in enumerate(expenses, 1):
        data.append([
            str(idx),
            exp.date,
            exp.time,
            f'₹{exp.amount:,.2f}',
            exp.purpose
        ])
    
    data.append(["", "", "TOTAL", f'₹{total_amount:,.2f}', ""])
    
    table = Table(data, colWidths=[40, 80, 80, 80, 200])
    
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('GRID', (0,0), (-1,-2), 1, colors.lightgrey),
        ('GRID', (0,-1), (-1,-1), 2, colors.black),
        ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (0,-1), 'CENTER'),
        ('ALIGN', (3,1), (3,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 6),
    ])
    
    # Alternate row colors
    for i in range(1, len(data)-1):
        if i % 2 == 0:
            style.add('BACKGROUND', (0,i), (-1,i), colors.whitesmoke)
    
    table.setStyle(style)
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    flash(f'PDF exported for {person}', 'success')
    return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)

@app.route('/clear_all')
@login_required
def clear_all():
    if request.args.get('confirm') == 'yes':
        num_deleted = Expense.query.delete()
        db.session.commit()
        flash(f'All {num_deleted} entries have been cleared', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/stats')
@login_required
def statistics():
    # Get monthly statistics
    expenses = Expense.query.all()
    
    monthly_stats = {}
    for exp in expenses:
        month = exp.date[:7]  # Get YYYY-MM
        if month not in monthly_stats:
            monthly_stats[month] = {
                'total': 0,
                'count': 0,
                'members': {}
            }
        monthly_stats[month]['total'] += exp.amount
        monthly_stats[month]['count'] += 1
        
        if exp.person not in monthly_stats[month]['members']:
            monthly_stats[month]['members'][exp.person] = 0
        monthly_stats[month]['members'][exp.person] += exp.amount
    
    return render_template('stats.html', 
                         monthly_stats=monthly_stats,
                         members=members)

# Initialize database and create tables
with app.app_context():
    init_db()
    # Optionally add some sample data if database is empty
    if Expense.query.count() == 0:
        print("No expenses found. Add some to get started!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)