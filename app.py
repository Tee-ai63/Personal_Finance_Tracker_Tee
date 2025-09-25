import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from supabase import create_client, Client
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

# --- Supabase Setup ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Functions ---
def add_record(record_type, category, amount):
    """Insert a new transaction into Supabase"""
    date = datetime.now().strftime("%Y-%m-%d")
    data = {"date": date, "type": record_type, "category": category, "amount": float(amount)}
    response = supabase.table("transactions").insert(data, returning="representation").execute()
    return response

def fetch_transactions(start_date=None, end_date=None):
    """Fetch transactions, optionally filtered by date range"""
    query = supabase.table("transactions").select("*").order("date", desc=True)
    if start_date and end_date:
        query = query.gte("date", start_date).lte("date", end_date)
    response = query.execute()
    return response.data

def show_summary(rows):
    """Calculate totals for income, expenses, and savings"""
    total_income, total_expense, total_savings = 0, 0, 0
    for t in rows:
        if t["type"] == "Income":
            total_income += t["amount"]
        elif t["type"] == "Expense":
            total_expense += t["amount"]
        elif t["type"] == "Savings":
            total_savings += t["amount"]
    balance = total_income - total_expense - total_savings
    return total_income, total_expense, total_savings, balance

def create_pie_chart(total_income, total_expense, total_savings):
    """Generate a pie chart of income vs expenses vs savings"""
    values = [total_income, total_expense, total_savings]
    labels = ["Income", "Expenses", "Savings"]
    fig, ax = plt.subplots()
    ax.pie(values, labels=labels, autopct="%1.1f%%")
    ax.set_title("Income vs Expenses vs Savings")
    return fig

def export_to_pdf(summary, transactions, fig=None):
    """Export finance summary + transactions + chart to PDF in memory"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = []

    total_income, total_expense, total_savings, balance = summary

    elements.append(Paragraph("Personal Finance Summary", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Total Income: {total_income}", styles["Normal"]))
    elements.append(Paragraph(f"Total Expense: {total_expense}", styles["Normal"]))
    elements.append(Paragraph(f"Total Savings: {total_savings}", styles["Normal"]))
    elements.append(Paragraph(f"Balance: {balance}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Add chart in memory
    if fig:
        chart_buf = BytesIO()
        fig.savefig(chart_buf, format="png")
        chart_buf.seek(0)
        elements.append(Image(chart_buf, width=400, height=300))
        elements.append(Spacer(1, 12))

    # Add transactions table
    if not transactions.empty:
        table_data = [["Date", "Type", "Category", "Amount"]] + transactions.values.tolist()
        elements.append(Table(table_data))
    else:
        elements.append(Paragraph("No transactions available.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- Streamlit UI ---
st.title("Personal Finance Tracker (Supabase + PDF)")

# Add new record
st.header("Add a Record")
record_type = st.radio("Select type:", ["Income", "Expense", "Savings"])
category = st.text_input("Category/Source:")
amount = st.number_input("Amount:", min_value=0.0, step=100.0)

if st.button("Add Record"):
    if category and amount > 0:
        response = add_record(record_type, category, amount)
        if response.data:
            st.success("Record added successfully!")
        else:
            st.error("Failed to add record.")
    else:
        st.error("Please enter a category and amount.")

# Show summary and transactions
st.header("Summary & Transactions")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=(datetime.now().date() - timedelta(days=30)))
with col2:
    end_date = st.date_input("End Date", value=datetime.now().date())

if st.button("Show Summary & Transactions"):
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    rows = fetch_transactions(start_date_str, end_date_str)
    total_income, total_expense, total_savings, balance = show_summary(rows)

    st.subheader("Summary")
    st.write(f"**Total Income:** {total_income}")
    st.write(f"**Total Expense:** {total_expense}")
    st.write(f"**Total Savings:** {total_savings}")
    st.write(f"**Balance (Income - Expense - Savings):** {balance}")

    fig = None
    if total_income + total_expense + total_savings > 0:
        fig = create_pie_chart(total_income, total_expense, total_savings)
        st.pyplot(fig)
    else:
        st.info("No transactions in this date range.")

    if rows:
        st.subheader("Transactions")
        df = pd.DataFrame(rows)[["date", "type", "category", "amount"]]
        st.dataframe(df, use_container_width=True)

        # PDF Download Button
        pdf_buffer = export_to_pdf((total_income, total_expense, total_savings, balance), df, fig)
        st.download_button(
            label="Download PDF",
            data=pdf_buffer,
            file_name="finance_summary.pdf",
            mime="application/pdf"
        )
    else:
        st.info("No transactions to display.")

