"""
Teacher Dashboard Page
View all students assigned to a specific teacher with subject filtering.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.database import get_all_students, get_db_connection

def show_teacher_dashboard():
    st.title("Teacher Dashboard")
    
    # Get all teachers
    students_df = get_all_students()
    if students_df.empty:
        st.warning("No students found.")
        return
    
    teachers = ['All'] + sorted([t for t in students_df['teacher_name'].dropna().unique() if t])
    selected_teacher = st.selectbox("Select Teacher", teachers)
    
    if selected_teacher == 'All':
        st.info("Please select a specific teacher to view their dashboard.")
        return
    
    # Subject filter
    subject_filter = st.radio("Subject", ["Both", "Math", "Reading"], horizontal=True)
    
    # Get students for this teacher
    teacher_students = students_df[students_df['teacher_name'] == selected_teacher]
    
    if teacher_students.empty:
        st.warning(f"No students found for {selected_teacher}.")
        return
    
    # Get latest scores
    conn = get_db_connection()
    
    # Math scores
    math_scores_df = pd.DataFrame()
    if subject_filter in ['Both', 'Math']:
        math_query = '''
            SELECT s.student_id, s.student_name, s.grade_level, s.class_name,
                   ms.overall_math_score, ms.risk_level, ms.assessment_period
            FROM students s
            LEFT JOIN math_scores ms ON s.student_id = ms.student_id
                AND ms.score_id = (
                    SELECT score_id FROM math_scores ms2
                    WHERE ms2.student_id = s.student_id
                    ORDER BY ms2.calculated_at DESC LIMIT 1)
            WHERE s.teacher_name = %s
        '''
        math_scores_df = pd.read_sql_query(math_query, conn, params=[selected_teacher])
    
    # Reading scores
    reading_scores_df = pd.DataFrame()
    if subject_filter in ['Both', 'Reading']:
        reading_query = '''
            SELECT s.student_id, s.student_name, s.grade_level, s.class_name,
                   ls.overall_literacy_score, ls.risk_level, ls.assessment_period
            FROM students s
            LEFT JOIN literacy_scores ls ON s.student_id = ls.student_id
                AND ls.score_id = (
                    SELECT score_id FROM literacy_scores ls2
                    WHERE ls2.student_id = s.student_id
                    ORDER BY ls2.calculated_at DESC LIMIT 1)
            WHERE s.teacher_name = %s
        '''
        reading_scores_df = pd.read_sql_query(reading_query, conn, params=[selected_teacher])
    
    conn.close()
    
    # Summary metrics
    st.markdown("")
    if subject_filter == 'Both':
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Students", len(teacher_students))
        with col2:
            math_with_scores = len(math_scores_df[math_scores_df['overall_math_score'].notna()]) if not math_scores_df.empty else 0
            st.metric("Math Assessed", math_with_scores)
        with col3:
            reading_with_scores = len(reading_scores_df[reading_scores_df['overall_literacy_score'].notna()]) if not reading_scores_df.empty else 0
            st.metric("Reading Assessed", reading_with_scores)
        with col4:
            math_needs_support = len(math_scores_df[math_scores_df['risk_level'].isin(['High', 'Medium'])]) if not math_scores_df.empty else 0
            reading_needs_support = len(reading_scores_df[reading_scores_df['risk_level'].isin(['High', 'Medium'])]) if not reading_scores_df.empty else 0
            st.metric("Needs Support", math_needs_support + reading_needs_support)
    elif subject_filter == 'Math':
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Students", len(teacher_students))
        with col2:
            math_with_scores = len(math_scores_df[math_scores_df['overall_math_score'].notna()]) if not math_scores_df.empty else 0
            st.metric("Assessed", math_with_scores)
        with col3:
            math_needs_support = len(math_scores_df[math_scores_df['risk_level'].isin(['High', 'Medium'])]) if not math_scores_df.empty else 0
            st.metric("Needs Support", math_needs_support)
    else:  # Reading
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Students", len(teacher_students))
        with col2:
            reading_with_scores = len(reading_scores_df[reading_scores_df['overall_literacy_score'].notna()]) if not reading_scores_df.empty else 0
            st.metric("Assessed", reading_with_scores)
        with col3:
            reading_needs_support = len(reading_scores_df[reading_scores_df['risk_level'].isin(['High', 'Medium'])]) if not reading_scores_df.empty else 0
            st.metric("Needs Support", reading_needs_support)
    
    # Student list
    st.markdown("")
    st.subheader("Students")
    
    if subject_filter == 'Both':
        # Combine math and reading data
        combined_df = teacher_students[['student_id', 'student_name', 'grade_level', 'class_name']].copy()
        
        if not math_scores_df.empty:
            math_df = math_scores_df[['student_id', 'overall_math_score', 'risk_level']].copy()
            math_df.columns = ['student_id', 'math_score', 'math_risk']
            combined_df = combined_df.merge(math_df, on='student_id', how='left')
        
        if not reading_scores_df.empty:
            reading_df = reading_scores_df[['student_id', 'overall_literacy_score', 'risk_level']].copy()
            reading_df.columns = ['student_id', 'reading_score', 'reading_risk']
            combined_df = combined_df.merge(reading_df, on='student_id', how='left')
        
        display_cols = ['student_name', 'grade_level', 'class_name']
        display_names = ['Student', 'Grade', 'Class']
        
        if 'math_score' in combined_df.columns:
            display_cols.append('math_score')
            display_names.append('Math Score')
        if 'reading_score' in combined_df.columns:
            display_cols.append('reading_score')
            display_names.append('Reading Score')
        
        display_df = combined_df[display_cols].copy()
        display_df.columns = display_names
        display_df['Math Score'] = display_df['Math Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
        display_df['Reading Score'] = display_df['Reading Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
        
        st.dataframe(display_df, width='stretch', height=400)
        
    elif subject_filter == 'Math':
        if not math_scores_df.empty:
            display_df = math_scores_df[['student_name', 'grade_level', 'class_name', 
                                        'overall_math_score', 'risk_level']].copy()
            display_df.columns = ['Student', 'Grade', 'Class', 'Math Score', 'Risk Level']
            display_df['Math Score'] = display_df['Math Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
            st.dataframe(display_df, width='stretch', height=400)
        else:
            st.info("No math scores available for this teacher's students.")
    else:  # Reading
        if not reading_scores_df.empty:
            display_df = reading_scores_df[['student_name', 'grade_level', 'class_name',
                                           'overall_literacy_score', 'risk_level']].copy()
            display_df.columns = ['Student', 'Grade', 'Class', 'Reading Score', 'Risk Level']
            display_df['Reading Score'] = display_df['Reading Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
            st.dataframe(display_df, width='stretch', height=400)
        else:
            st.info("No reading scores available for this teacher's students.")
    
    # Quick links to student detail pages
    st.markdown("")
    st.subheader("Quick Actions")
    st.info("💡 Use the navigation menu to view detailed student profiles for Math or Reading.")
