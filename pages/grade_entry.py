"""
Grade Entry Page
Allows teachers to enter assessment scores and interventions
Supports both single student and bulk entry modes
"""
import streamlit as st
import pandas as pd
from database import (
    get_all_students, create_student, add_assessment, add_intervention,
    get_student_id, get_db_connection
)
from calculations import process_assessment_score
from utils import recalculate_literacy_scores
from datetime import datetime

def show_grade_entry():
    st.title("✏️ Grade Entry")
    st.caption("Keyboard-first workflow: paste rows into the bulk grid and use tab/arrow keys to move quickly.")
    st.markdown("---")
    
    # Mode selection
    entry_mode = st.radio(
        "Entry Mode",
        ["Single Student Entry", "Bulk Entry"],
        horizontal=True
    )
    
    st.markdown("---")
    
    if entry_mode == "Single Student Entry":
        show_single_entry_form()
    else:
        show_bulk_entry_form()

def show_single_entry_form():
    """Single student entry form"""
    st.subheader("Single Student Entry")
    
    # Get existing students
    students_df = get_all_students()
    
    # Student selection or creation
    student_option = st.radio(
        "Student",
        ["Select Existing Student", "Create New Student"],
        horizontal=True
    )
    
    if student_option == "Select Existing Student":
        if students_df.empty:
            st.warning("No students found. Please create a new student.")
            student_id = None
            student_name = None
            grade_level = None
            school_year = None
        else:
            # First: Select student name (unique names only)
            unique_students = sorted(students_df['student_name'].unique().tolist())
            selected_student_name = st.selectbox(
                "Select Student *",
                unique_students,
                key="entry_student_select"
            )
            
            # Second: Select grade level
            grade_level = st.selectbox(
                "Select Grade Level *",
                ["Kindergarten", "First", "Second", "Third", "Fourth"],
                key="entry_grade_select"
            )
            
            # Third: Select school year
            school_year = st.selectbox(
                "School Year *",
                ["2024-25", "2023-24", "2025-26"],
                index=0,
                key="entry_year_select"
            )
            
            # Get or create student record for this combination
            student_id = get_student_id(selected_student_name, grade_level, school_year)
            student_name = selected_student_name
            
            # If student doesn't exist for this grade/year, show option to create
            if not student_id:
                st.info(f"⚠️ {selected_student_name} doesn't have a record for {grade_level} ({school_year}). Click 'Create Record' below or fill in class/teacher info.")
                
                col1, col2 = st.columns(2)
                with col1:
                    class_name = st.text_input("Class Name", key="entry_class_name")
                with col2:
                    teacher_name = st.text_input("Teacher Name", key="entry_teacher_name")
                
                if st.button("Create Record", key="create_record_btn"):
                    student_id = create_student(
                        student_name=selected_student_name,
                        grade_level=grade_level,
                        class_name=class_name if class_name else None,
                        teacher_name=teacher_name if teacher_name else None,
                        school_year=school_year
                    )
                    st.success(f"Created record for {selected_student_name} - {grade_level}")
                    st.rerun()
            else:
                # Get existing student info
                student_row = students_df[
                    (students_df['student_name'] == selected_student_name) &
                    (students_df['grade_level'] == grade_level) &
                    (students_df['school_year'] == school_year)
                ].iloc[0]
                
                # Show current class/teacher (can be edited)
                col1, col2 = st.columns(2)
                with col1:
                    class_name = st.text_input(
                        "Class Name", 
                        value=student_row.get('class_name', '') or '',
                        key="entry_class_name"
                    )
                with col2:
                    teacher_name = st.text_input(
                        "Teacher Name",
                        value=student_row.get('teacher_name', '') or '',
                        key="entry_teacher_name"
                    )
    else:
        # Create new student form
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            student_name = st.text_input("Student Name *", key="new_student_name")
        with col2:
            grade_level = st.selectbox(
                "Grade Level *",
                ["Kindergarten", "First", "Second", "Third", "Fourth"],
                key="new_grade_level"
            )
        with col3:
            class_name = st.text_input("Class Name", key="new_class_name")
        with col4:
            teacher_name = st.text_input("Teacher Name", key="new_teacher_name")
        
        school_year = st.selectbox(
            "School Year",
            ["2024-25", "2023-24", "2025-26"],
            index=0,
            key="new_school_year"
        )
        
        student_id = None
    
    # Assessment Information
    st.markdown("### Assessment Information")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        assessment_type = st.selectbox(
            "Assessment Type *",
            [
                "Reading_Level",
                "Sight_Words",
                "Spelling",
                "Spelling_Inventory",
                "Benchmark",
                "Easy_CBM",
                "Phonics_Survey"
            ]
        )
    
    with col2:
        assessment_period = st.selectbox(
            "Assessment Period *",
            ["Fall", "Winter", "Spring", "EOY"]
        )
    
    with col3:
        assessment_date = st.date_input(
            "Assessment Date",
            value=datetime.now().date(),
            key="assessment_date"
        )
    
    # Use school_year from above
    school_year_display = school_year if 'school_year' in locals() else "2024-25"
    
    # Score Entry (dynamic based on assessment type)
    st.markdown("### Score Entry")
    
    score_value = None
    score_normalized = None
    
    if assessment_type == "Reading_Level":
        reading_levels = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 
                          'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']
        selected_level = st.selectbox("Reading Level", reading_levels)
        score_value = selected_level
        score_normalized = process_assessment_score(assessment_type, score_value)
    
    elif assessment_type == "Sight_Words":
        col1, col2 = st.columns(2)
        with col1:
            sight_words_count = st.number_input("Sight Words Count", min_value=0, value=0)
        with col2:
            max_sight_words = st.number_input("Max Possible", min_value=1, value=200)
        score_value = f"{sight_words_count}/{max_sight_words}"
        score_normalized = process_assessment_score(assessment_type, score_value)
    
    elif assessment_type in ["Spelling", "Spelling_Inventory"]:
        col1, col2 = st.columns(2)
        with col1:
            correct = st.number_input("Correct", min_value=0, value=0)
        with col2:
            total = st.number_input("Total", min_value=1, value=15)
        score_value = f"{correct}/{total}"
        score_normalized = process_assessment_score(assessment_type, score_value)
    
    elif assessment_type in ["Benchmark", "Easy_CBM"]:
        score_value = st.number_input("Score (0-100)", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
        score_normalized = float(score_value)
    
    elif assessment_type == "Phonics_Survey":
        score_value = st.text_input("Phonics Score (e.g., 14/15 or percentage)")
        score_normalized = process_assessment_score(assessment_type, score_value)
    
    # Additional Fields
    st.markdown("### Additional Information")
    
    notes = st.text_area("Notes/Observations", height=100)
    concerns = st.text_area("Concerns", height=100)
    needs_review = st.checkbox("Flag as needs review")
    save_as_draft = st.checkbox("Save draft (exclude from finalized reporting)")
    entered_by = st.text_input("Entered By", value="Teacher")
    

    # Outlier detection against recent history
    if student_id and score_normalized is not None:
        conn = get_db_connection()
        prev_df = pd.read_sql_query(
            "SELECT score_normalized FROM assessments WHERE student_id = ? AND assessment_type = ? ORDER BY created_at DESC LIMIT 5",
            conn, params=[student_id, assessment_type]
        )
        conn.close()
        if not prev_df.empty and pd.notna(prev_df['score_normalized'].std()) and prev_df['score_normalized'].std() > 0:
            zscore = (score_normalized - prev_df['score_normalized'].mean()) / prev_df['score_normalized'].std()
            if abs(zscore) >= 2:
                st.warning(f"This score appears to be an outlier vs prior scores (z={zscore:.2f}). Please confirm.")

    # Intervention Section
    st.markdown("### Intervention Entry (Optional)")
    
    add_intervention_entry = st.checkbox("Add Intervention Entry")
    
    intervention_type = None
    intervention_start_date = None
    intervention_end_date = None
    intervention_frequency = None
    intervention_duration = None
    intervention_status = None
    intervention_notes = None
    
    if add_intervention_entry:
        col1, col2 = st.columns(2)
        
        with col1:
            intervention_type = st.selectbox(
                "Intervention Type",
                [
                    "Small_Group_Reading",
                    "One_on_One_Tutoring",
                    "Phonics_Program",
                    "Reading_Recovery",
                    "RTI_Services",
                    "Pull_Out_Services",
                    "Other"
                ]
            )
            
            intervention_start_date = st.date_input("Start Date", value=datetime.now().date())
            intervention_end_date = st.date_input("End Date (optional)", value=None)
            
            intervention_frequency = st.selectbox(
                "Frequency",
                ["Daily", "3x_week", "Weekly", "Bi-weekly", "Other"]
            )
        
        with col2:
            intervention_duration = st.number_input("Duration (minutes per session)", min_value=1, value=30)
            intervention_status = st.selectbox("Status", ["Active", "Completed", "Discontinued"])
            intervention_notes = st.text_area("Intervention Notes", height=100)
    
    # Submit Button
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("Save Assessment", type="primary", use_container_width=True):
            if student_option == "Create New Student":
                if not student_name or not grade_level:
                    st.error("Please fill in required fields: Student Name and Grade Level")
                else:
                    student_id = create_student(
                        student_name=student_name,
                        grade_level=grade_level,
                        class_name=class_name if class_name else None,
                        teacher_name=teacher_name if teacher_name else None,
                        school_year=school_year_display
                    )
                    st.success(f"Created student: {student_name}")
            
            # If selecting existing student but record doesn't exist yet
            elif student_option == "Select Existing Student" and not student_id:
                if not student_name or not grade_level:
                    st.error("Please select student and grade level")
                else:
                    # Create the record
                    student_id = create_student(
                        student_name=student_name,
                        grade_level=grade_level,
                        class_name=class_name if class_name else None,
                        teacher_name=teacher_name if teacher_name else None,
                        school_year=school_year_display
                    )
                    st.success(f"Created record for {student_name} - {grade_level}")
            
            # Update class/teacher if changed
            if student_id and student_option == "Select Existing Student":
                # Update student record if class/teacher changed
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE students 
                    SET class_name = ?, teacher_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                ''', (class_name if class_name else None, teacher_name if teacher_name else None, student_id))
                conn.commit()
                conn.close()
            
            if student_id:
                # Add assessment
                add_assessment(
                    student_id=student_id,
                    assessment_type=assessment_type,
                    assessment_period=assessment_period,
                    school_year=school_year_display,
                    score_value=str(score_value) if score_value else None,
                    score_normalized=score_normalized,
                    assessment_date=assessment_date.strftime("%Y-%m-%d") if assessment_date else None,
                    notes=notes if notes else None,
                    concerns=concerns if concerns else None,
                    entered_by=entered_by,
                    needs_review=needs_review,
                    is_draft=save_as_draft
                )
                
                # Add intervention if specified
                if add_intervention_entry and intervention_type:
                    add_intervention(
                        student_id=student_id,
                        intervention_type=intervention_type,
                        start_date=intervention_start_date.strftime("%Y-%m-%d") if intervention_start_date else None,
                        end_date=intervention_end_date.strftime("%Y-%m-%d") if intervention_end_date else None,
                        frequency=intervention_frequency,
                        duration_minutes=intervention_duration,
                        status=intervention_status,
                        notes=intervention_notes
                    )
                
                # Recalculate literacy scores
                recalculate_literacy_scores(student_id=student_id)
                
                st.success("Assessment saved successfully!")
                st.rerun()
            else:
                st.error("Please select or create a student first")
    
    with col2:
        if st.button("Save and Add Another", use_container_width=True):
            if student_option == "Create New Student":
                if not student_name or not grade_level:
                    st.error("Please fill in required fields: Student Name and Grade Level")
                else:
                    student_id = create_student(
                        student_name=student_name,
                        grade_level=grade_level,
                        class_name=class_name if class_name else None,
                        teacher_name=teacher_name if teacher_name else None,
                        school_year=school_year_display
                    )
                    st.success(f"Created student: {student_name}")

            # If selecting existing student but record doesn't exist yet
            elif student_option == "Select Existing Student" and not student_id:
                if not student_name or not grade_level:
                    st.error("Please select student and grade level")
                else:
                    student_id = create_student(
                        student_name=student_name,
                        grade_level=grade_level,
                        class_name=class_name if class_name else None,
                        teacher_name=teacher_name if teacher_name else None,
                        school_year=school_year_display
                    )
                    st.success(f"Created record for {student_name} - {grade_level}")

            # Update class/teacher if changed
            if student_id and student_option == "Select Existing Student":
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE students 
                    SET class_name = ?, teacher_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                ''', (class_name if class_name else None, teacher_name if teacher_name else None, student_id))
                conn.commit()
                conn.close()

            if student_id:
                # Add assessment
                add_assessment(
                    student_id=student_id,
                    assessment_type=assessment_type,
                    assessment_period=assessment_period,
                    school_year=school_year_display,
                    score_value=str(score_value) if score_value else None,
                    score_normalized=score_normalized,
                    assessment_date=assessment_date.strftime("%Y-%m-%d") if assessment_date else None,
                    notes=notes if notes else None,
                    concerns=concerns if concerns else None,
                    entered_by=entered_by
                )

                # Add intervention if specified
                if add_intervention_entry and intervention_type:
                    add_intervention(
                        student_id=student_id,
                        intervention_type=intervention_type,
                        start_date=intervention_start_date.strftime("%Y-%m-%d") if intervention_start_date else None,
                        end_date=intervention_end_date.strftime("%Y-%m-%d") if intervention_end_date else None,
                        frequency=intervention_frequency,
                        duration_minutes=intervention_duration,
                        status=intervention_status,
                        notes=intervention_notes
                    )

                # Recalculate literacy scores
                recalculate_literacy_scores(student_id=student_id)
                st.success("Assessment saved successfully! Enter another one below.")
            else:
                st.error("Please select or create a student first")

def show_bulk_entry_form():
    """Bulk entry form"""
    st.subheader("Bulk Entry")
    
    # Template download
    st.info("💡 Download the template Excel file to fill in multiple students at once.")
    
    # Create template
    template_df = pd.DataFrame({
        'Student_Name': [''],
        'Grade_Level': [''],
        'Class_Name': [''],
        'Teacher_Name': [''],
        'Assessment_Type': ['Reading_Level'],
        'Assessment_Period': ['Fall'],
        'Score_Value': [''],
        'Notes': [''],
        'Concerns': ['']
    })
    
    csv_template = template_df.to_csv(index=False)
    st.download_button(
        label="Download Template CSV",
        data=csv_template,
        file_name="bulk_entry_template.csv",
        mime="text/csv"
    )
    

    st.markdown("### Quick Bulk Grid (copy/paste)")
    if 'bulk_grid' not in st.session_state:
        st.session_state.bulk_grid = pd.DataFrame([{
            'Student_Name':'', 'Grade_Level':'', 'Class_Name':'', 'Teacher_Name':'',
            'Assessment_Type':'Reading_Level', 'Assessment_Period':'Fall', 'Score_Value':'',
            'Needs_Review':False, 'Save_Draft':False, 'Notes':'', 'Concerns':''
        } for _ in range(8)])
    st.session_state.bulk_grid = st.data_editor(st.session_state.bulk_grid, num_rows='dynamic', use_container_width=True)
    if st.button('Save Grid Entries', use_container_width=True):
        grid_saved, grid_errors = 0, 0
        for _, row in st.session_state.bulk_grid.iterrows():
            try:
                if str(row.get('Student_Name','')).strip() == '' or str(row.get('Grade_Level','')).strip() == '':
                    continue
                sid = get_student_id(str(row.get('Student_Name')).strip(), str(row.get('Grade_Level')).strip(), '2024-25')
                if not sid:
                    sid = create_student(str(row.get('Student_Name')).strip(), str(row.get('Grade_Level')).strip(), str(row.get('Class_Name','')).strip() or None, str(row.get('Teacher_Name','')).strip() or None, '2024-25')
                raw_score = str(row.get('Score_Value','')).strip()
                norm = process_assessment_score(str(row.get('Assessment_Type')).strip(), raw_score) if raw_score else None
                add_assessment(
                    student_id=sid,
                    assessment_type=str(row.get('Assessment_Type')).strip(),
                    assessment_period=str(row.get('Assessment_Period')).strip(),
                    school_year='2024-25',
                    score_value=raw_score or None,
                    score_normalized=norm,
                    notes=str(row.get('Notes','')).strip() or None,
                    concerns=str(row.get('Concerns','')).strip() or None,
                    entered_by='Teacher',
                    needs_review=bool(row.get('Needs_Review', False)),
                    is_draft=bool(row.get('Save_Draft', False))
                )
                grid_saved += 1
            except Exception:
                grid_errors += 1
        if grid_saved:
            recalculate_literacy_scores()
        st.success(f'Grid saved: {grid_saved} entries')
        if grid_errors:
            st.warning(f'Grid errors: {grid_errors}')

    st.markdown("---")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file",
        type=['csv', 'xlsx'],
        help="Upload a file with student assessment data"
    )
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                bulk_df = pd.read_csv(uploaded_file)
            else:
                bulk_df = pd.read_excel(uploaded_file)
            
            st.success(f"File loaded: {len(bulk_df)} rows")
            
            # Show preview
            st.subheader("Data Preview")
            st.dataframe(bulk_df.head(10), use_container_width=True)
            
            # Bulk entry settings
            st.markdown("### Entry Settings")
            
            col1, col2 = st.columns(2)
            
            with col1:
                default_school_year = st.selectbox(
                    "Default School Year",
                    ["2024-25", "2023-24", "2025-26"],
                    index=0
                )
                default_entered_by = st.text_input("Entered By", value="Teacher")
            
            with col2:
                auto_create_students = st.checkbox("Auto-create students if not found", value=True)
                validate_before_save = st.checkbox("Validate before saving", value=True)
            
            # Validate data
            if validate_before_save:
                errors = []
                required_cols = ['Student_Name', 'Grade_Level', 'Assessment_Type', 'Assessment_Period']
                
                for col in required_cols:
                    if col not in bulk_df.columns:
                        errors.append(f"Missing required column: {col}")
                
                if errors:
                    st.error("Validation errors found:")
                    for error in errors:
                        st.error(f"- {error}")
                else:
                    st.success("✓ Data validation passed")
            
            # Save button
            if st.button("Save All Entries", type="primary", use_container_width=True):
                saved_count = 0
                error_count = 0
                
                for idx, row in bulk_df.iterrows():
                    try:
                        # Get or create student
                        student_name = str(row.get('Student_Name', '')).strip()
                        grade_level = str(row.get('Grade_Level', '')).strip()
                        class_name = str(row.get('Class_Name', '')).strip() if pd.notna(row.get('Class_Name')) else None
                        teacher_name = str(row.get('Teacher_Name', '')).strip() if pd.notna(row.get('Teacher_Name')) else None
                        
                        if not student_name or not grade_level:
                            error_count += 1
                            continue
                        
                        student_id = get_student_id(student_name, grade_level, default_school_year)
                        
                        if not student_id and auto_create_students:
                            student_id = create_student(
                                student_name=student_name,
                                grade_level=grade_level,
                                class_name=class_name,
                                teacher_name=teacher_name,
                                school_year=default_school_year
                            )
                        
                        if student_id:
                            assessment_type = str(row.get('Assessment_Type', '')).strip()
                            assessment_period = str(row.get('Assessment_Period', '')).strip()
                            score_value = str(row.get('Score_Value', '')) if pd.notna(row.get('Score_Value')) else None
                            notes = str(row.get('Notes', '')) if pd.notna(row.get('Notes')) else None
                            concerns = str(row.get('Concerns', '')) if pd.notna(row.get('Concerns')) else None
                            
                            if assessment_type and assessment_period:
                                score_normalized = process_assessment_score(assessment_type, score_value) if score_value else None
                                
                                add_assessment(
                                    student_id=student_id,
                                    assessment_type=assessment_type,
                                    assessment_period=assessment_period,
                                    school_year=default_school_year,
                                    score_value=score_value,
                                    score_normalized=score_normalized,
                                    assessment_date=None,
                                    notes=notes,
                                    concerns=concerns,
                                    entered_by=default_entered_by,
                                    needs_review=bool(row.get("Needs_Review", False)),
                                    is_draft=bool(row.get("Save_Draft", False))
                                )
                                saved_count += 1
                            else:
                                error_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        error_count += 1
                        st.warning(f"Error processing row {idx + 1}: {str(e)}")
                
                # Recalculate literacy scores for all affected students
                if saved_count > 0:
                    recalculate_literacy_scores()
                
                st.success(f"Saved {saved_count} entries successfully!")
                if error_count > 0:
                    st.warning(f"{error_count} entries had errors and were skipped.")
                
                st.rerun()
        
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
