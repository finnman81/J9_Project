"""
Main Streamlit application for School Assessment System
Supports both Math and Reading/Literacy assessments
"""
import streamlit as st
import pandas as pd
from core.database import init_database, get_db_connection

# Page configuration
st.set_page_config(
    page_title="School Assessment System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database on first run
if 'db_initialized' not in st.session_state:
    init_database()
    st.session_state.db_initialized = True

# Sidebar navigation
st.sidebar.title("📊 School Assessment System")
st.sidebar.markdown("---")

# Subject selection
subject = st.sidebar.radio(
    "Subject",
    ["Math", "Reading"],
    key="subject_select"
)

st.sidebar.markdown("---")

# Page selection based on subject
if subject == "Math":
    page = st.sidebar.radio(
        "Navigation",
        ["Overview Dashboard", "Student Detail", "Grade Entry", "Teacher Dashboard"],
        key="math_nav"
    )
    
    # Route to appropriate page
    if page == "Overview Dashboard":
        from pages.math_overview_dashboard import show_math_overview_dashboard
        show_math_overview_dashboard()
    elif page == "Student Detail":
        from pages.math_student_detail import show_math_student_detail
        show_math_student_detail()
    elif page == "Grade Entry":
        from pages.grade_entry import show_grade_entry
        show_grade_entry()
    elif page == "Teacher Dashboard":
        from pages.teacher_dashboard import show_teacher_dashboard
        show_teacher_dashboard()
else:  # Reading
    page = st.sidebar.radio(
        "Navigation",
        ["Overview Dashboard", "Student Detail", "Grade Entry", "Teacher Dashboard"],
        key="reading_nav"
    )
    
    # Route to appropriate page
    if page == "Overview Dashboard":
        from pages.overview_dashboard import show_overview_dashboard
        show_overview_dashboard()
    elif page == "Student Detail":
        from pages.student_detail import show_student_detail
        show_student_detail()
    elif page == "Grade Entry":
        from pages.grade_entry import show_grade_entry
        show_grade_entry()
    elif page == "Teacher Dashboard":
        from pages.teacher_dashboard import show_teacher_dashboard
        show_teacher_dashboard()
