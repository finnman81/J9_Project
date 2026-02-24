# K-12 private school prospects — v2 changelog

Date: 2026-02-22/23

## What changed vs v1 (per request)
- **Expanded NJ coverage**: built v2 list with **~20 NJ schools** (target was 15–25), while keeping the overall list in the **30–50** range (v2 has **34 total** across **NJ/NY/CT/PA/VA**).
- **Applied exclusion filters**: removed/avoided **religious/faith-based**, **Quaker/Friends**, **Montessori**, **Waldorf**, and **special-ed-focused** schools.
  - During QA, replaced **Eagle Hill School (CT)** (learning-differences focus concern) with **Hamden Hall Country Day School (CT)**.
- **Reworked POC requirements**:
  - POC role biased toward academic/senior leadership (Head of School used when no clear Academic Dean/Principal page was quickly verifiable).
  - **Each row includes at least one of:** a **LinkedIn Profile URL** *or* an on-site **POC Profile URL** (leadership bio page), to satisfy the “profile link required” constraint.
  - **Public Email** populated only where a **publicly listed** email address was available (commonly Admissions/Contact addresses).
- **Updated columns** to the exact schema requested:
  - School Name, Website, City, State, Grades, Day/Boarding, Enrollment, Nonsectarian Confirm, LinkedIn School URL, Contact Page URL, Staff Directory URL, Primary POC Name, Primary POC Title, Public Email, LinkedIn Profile URL, POC Profile URL, Notes

## Notes / caveats
- **Enrollment figures** are best-effort and often sourced from association directory/Wikipedia/commonly published school facts; some are marked **approx/verify** in Notes.
- **Nonsectarian Confirm** is marked **Yes** when the school is commonly described as independent/nonsectarian and/or states nonsectarian on its site/directory; recommend spot-checking the handful of “large/legacy” schools.
- The dataset intentionally **favors enrollment <500**, but includes some higher-enrollment independents to maintain geographic coverage and well-known anchors.

Output written to:
- `/data/.openclaw/workspace/outputs/k12_private_schools_prospects_raw_30_50_v2.csv`
