"""
Data Import Page
Allows importing Excel data (normalized_grades.xlsx format) into the database
"""
import streamlit as st
import pandas as pd
from database import (
    init_database, create_student, add_assessment, save_literacy_score,
    get_student_assessments, get_student_id
)
from calculations import (
    process_assessment_score, calculate_component_scores,
    calculate_overall_literacy_score, determine_risk_level, calculate_trend
)
from utils import recalculate_literacy_scores

def show_data_import():
    st.title("📥 Data Import")
    st.markdown("---")
    st.info("💡 Upload your `normalized_grades.xlsx` file to import all student data and assessments at once.")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Excel file (normalized_grades.xlsx)",
        type=['xlsx', 'xls'],
        help="Upload the normalized grades Excel file to import all data"
    )
    
    if uploaded_file:
        try:
            # Read Excel file
            df = pd.read_excel(uploaded_file)
            st.success(f"✅ File loaded: {len(df)} records found")
            
            # Show preview
            st.subheader("Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            # Enhancement: Mapping wizard
            st.subheader("Mapping Wizard")
            target_fields = ['Student_Name','Grade_Level','Concerns']
            mapping_cols = ['<skip>'] + list(df.columns)
            selected_mappings = {}
            map_col1, map_col2, map_col3 = st.columns(3)
            for i, field in enumerate(target_fields):
                with [map_col1, map_col2, map_col3][i % 3]:
                    selected_mappings[field] = st.selectbox(f"{field} ←", mapping_cols, index=(mapping_cols.index(field) if field in mapping_cols else 0), key=f"import_map_{field}")

            mapped_preview = pd.DataFrame()
            for field, source in selected_mappings.items():
                mapped_preview[field] = df[source] if source != '<skip>' and source in df.columns else None
            st.caption("Mapped preview")
            st.dataframe(mapped_preview.head(8), use_container_width=True)
            
            # School year selection
            school_year = st.selectbox(
                "School Year",
                ["2024-25", "2023-24", "2025-26"],
                index=0
            )
            
            # Assessment mappings (from migrate_data.py)
            assessment_mappings = {
                'Reading_Level_Fall': ('Reading_Level', 'Fall'),
                'Reading_Level_Winter': ('Reading_Level', 'Winter'),
                'Reading_Level_Spring': ('Reading_Level', 'Spring'),
                'Reading_Level_EOY': ('Reading_Level', 'EOY'),
                'Reading_Level_1EOY': ('Reading_Level', 'EOY'),
                'Reading_Level_2EOY': ('Reading_Level', 'EOY'),
                'Reading_Level_3EOY': ('Reading_Level', 'EOY'),
                'Sight_Words_SeptNov': ('Sight_Words', 'Fall'),
                'Sight_Words_Winter': ('Sight_Words', 'Winter'),
                'Sight_Words_Spring': ('Sight_Words', 'Spring'),
                'Sight_Words_EOY': ('Sight_Words', 'EOY'),
                'Spelling_Fall': ('Spelling', 'Fall'),
                'Spelling_Spring': ('Spelling', 'Spring'),
                'Spelling_EOY': ('Spelling', 'EOY'),
                'Benchmark_Fall': ('Benchmark', 'Fall'),
                'Benchmark_Spring': ('Benchmark', 'Spring'),
                'Alphabet_Naming': ('Phonics_Survey', 'Fall'),
                'Slingerlands_Fall': ('Phonics_Survey', 'Fall'),
                'PAR_Fall': ('Benchmark', 'Fall'),
                'PAR_EOY': ('Benchmark', 'EOY'),
            }
            
            # Enhancement: Duplicate detection (same student + same measure + same date if date column exists)
            potential_duplicate_rows = pd.DataFrame()
            if {"Student_Name", "Assessment_Date"}.issubset(set(df.columns)):
                measure_cols = [c for c in df.columns if c not in ["Student_Name", "Grade_Level", "Concerns"] and not c.endswith("_Original")]
                long_parts = []
                for mc in measure_cols:
                    part = df[["Student_Name", "Assessment_Date", mc]].copy()
                    part = part.rename(columns={mc: "Score_Value"})
                    part["Measure"] = mc
                    long_parts.append(part)
                if long_parts:
                    long_df = pd.concat(long_parts, ignore_index=True)
                    long_df = long_df[long_df["Score_Value"].notna()]
                    dup_mask = long_df.duplicated(subset=["Student_Name", "Measure", "Assessment_Date"], keep=False)
                    potential_duplicate_rows = long_df[dup_mask]
            if not potential_duplicate_rows.empty:
                st.warning(f"Detected {len(potential_duplicate_rows)} potential duplicate assessment entries in file.")
                st.dataframe(potential_duplicate_rows.head(20), use_container_width=True)

            # Import button
            if st.button("Import All Data", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                students_created = set()
                assessments_added = 0
                errors = []
                
                total_rows = len(df)
                
                for idx, row in df.iterrows():
                    try:
                        # Update progress
                        progress = (idx + 1) / total_rows
                        progress_bar.progress(progress)
                        status_text.text(f"Processing row {idx + 1} of {total_rows}...")
                        
                        student_name = str(row['Student_Name']).strip()
                        grade_level = str(row['Grade_Level']).strip()
                        
                        # Create student (if not already created)
                        student_key = (student_name, grade_level, school_year)
                        if student_key not in students_created:
                            student_id = create_student(
                                student_name=student_name,
                                grade_level=grade_level,
                                class_name=None,
                                teacher_name=None,
                                school_year=school_year
                            )
                            students_created.add(student_key)
                        else:
                            student_id = get_student_id(student_name, grade_level, school_year)
                        
                        # Process each assessment column
                        for col in df.columns:
                            if col in ['Student_Name', 'Grade_Level', 'Concerns']:
                                continue
                            
                            # Skip original columns
                            if col.endswith('_Original'):
                                continue
                            
                            # Check if this column maps to an assessment
                            if col in assessment_mappings:
                                assessment_type, period = assessment_mappings[col]
                                score_value = row[col]
                                
                                # Only add if score exists
                                if pd.notna(score_value) and str(score_value).strip() != '':
                                    # Normalize score
                                    score_normalized = process_assessment_score(assessment_type, str(score_value))
                                    
                                    # Add assessment
                                    add_assessment(
                                        student_id=student_id,
                                        assessment_type=assessment_type,
                                        assessment_period=period,
                                        school_year=school_year,
                                        score_value=str(score_value),
                                        score_normalized=score_normalized,
                                        assessment_date=None,
                                        notes=None,
                                        concerns=str(row.get('Concerns', '')) if pd.notna(row.get('Concerns')) else None,
                                        entered_by='Data Import'
                                    )
                                    assessments_added += 1
                        
                        # Calculate and save literacy score for each period
                        student_assessments = get_student_assessments(student_id, school_year)
                        
                        for period in ['Fall', 'Winter', 'Spring', 'EOY']:
                            period_assessments = student_assessments[student_assessments['assessment_period'] == period]
                            if not period_assessments.empty:
                                components = calculate_component_scores(period_assessments, period)
                                overall_score, component_scores = calculate_overall_literacy_score(components)
                                
                                if overall_score is not None:
                                    risk_level = determine_risk_level(overall_score)
                                    
                                    # Calculate trend
                                    trend = 'Unknown'
                                    if period != 'Fall':
                                        prev_period = 'Fall' if period == 'Winter' else ('Winter' if period == 'Spring' else 'Spring')
                                        prev_assessments = student_assessments[student_assessments['assessment_period'] == prev_period]
                                        if not prev_assessments.empty:
                                            prev_components = calculate_component_scores(prev_assessments, prev_period)
                                            prev_overall, _ = calculate_overall_literacy_score(prev_components)
                                            if prev_overall is not None:
                                                trend = calculate_trend(overall_score, prev_overall)
                                    
                                    save_literacy_score(
                                        student_id=student_id,
                                        school_year=school_year,
                                        assessment_period=period,
                                        overall_score=overall_score,
                                        reading_component=component_scores.get('reading'),
                                        phonics_component=component_scores.get('phonics_spelling'),
                                        spelling_component=component_scores.get('phonics_spelling'),
                                        sight_words_component=component_scores.get('sight_words'),
                                        risk_level=risk_level,
                                        trend=trend
                                    )
                    
                    except Exception as e:
                        errors.append(f"Row {idx + 1} ({row.get('Student_Name', 'Unknown')}): {str(e)}")
                
                # Recalculate all literacy scores
                recalculate_literacy_scores()
                
                # Show results
                progress_bar.empty()
                status_text.empty()
                
                st.success(f"""
                ✅ **Import Complete!**
                - Students created: {len(students_created)}
                - Assessments added: {assessments_added}
                """)
                st.subheader("Import Quality Report")
                st.write(f"Rows imported: {assessments_added}")
                st.write(f"Rows skipped: {len(errors)}")
                
                if errors:
                    st.warning(f"⚠️ {len(errors)} errors occurred:")
                    for error in errors[:10]:  # Show first 10 errors
                        st.text(error)
                    if len(errors) > 10:
                        st.text(f"... and {len(errors) - 10} more errors")
                
                st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            st.exception(e)
