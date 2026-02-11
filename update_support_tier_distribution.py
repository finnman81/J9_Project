"""
Update literacy_scores so Support Tiers show ~15 Intensive, most Core.
Run once: python update_support_tier_distribution.py
"""
import random
from database import get_db_connection
import pandas as pd

random.seed(42)

conn = get_db_connection()

# Latest score per student for most recent school year (the one the dashboard uses)
q = """
    WITH latest AS (
        SELECT score_id, student_id, school_year, overall_literacy_score, risk_level,
               ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY calculated_at DESC) AS rn
        FROM literacy_scores
        WHERE school_year = (SELECT MAX(school_year) FROM literacy_scores)
    )
    SELECT score_id, student_id, school_year, overall_literacy_score, risk_level
    FROM latest WHERE rn = 1
"""
df = pd.read_sql_query(q, conn)
if df.empty:
    print("No literacy_scores found.")
    conn.close()
    exit(0)

n = len(df)
# Target: ~15 Intensive, ~10 Strategic, rest Core
n_intensive = min(15, max(0, n - 20))
n_strategic = min(12, n - n_intensive - 5)
n_core = n - n_intensive - n_strategic

# Shuffle and assign
idx = df.index.tolist()
random.shuffle(idx)
intensive_idx = idx[:n_intensive]
strategic_idx = idx[n_intensive : n_intensive + n_strategic]
core_idx = idx[n_intensive + n_strategic :]

def risk_for_score(score):
    if score < 50: return 'High'
    if score < 70: return 'Medium'
    return 'Low'

updates = []
for i in intensive_idx:
    score = round(random.uniform(35, 49), 1)
    updates.append((score, risk_for_score(score), int(df.loc[i, 'score_id'])))
for i in strategic_idx:
    score = round(random.uniform(55, 69), 1)
    updates.append((score, risk_for_score(score), int(df.loc[i, 'score_id'])))
for i in core_idx:
    score = round(random.uniform(72, 98), 1)
    updates.append((score, risk_for_score(score), int(df.loc[i, 'score_id'])))

cur = conn.cursor()
for overall_score, risk_level, score_id in updates:
    cur.execute('''
        UPDATE literacy_scores
        SET overall_literacy_score = %s, risk_level = %s, calculated_at = NOW()
        WHERE score_id = %s
    ''', (overall_score, risk_level, score_id))
conn.commit()
conn.close()

print(f"Updated {len(updates)} literacy_scores: {n_intensive} Intensive, {n_strategic} Strategic, {n_core} Core.")
print("Support Tiers should now show ~15 Intensive and most Core.")
