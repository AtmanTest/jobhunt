#!/usr/bin/env python3
"""Generate English CV PDF from cv_data.py"""

from fpdf import FPDF
import os

from cv_data import CV

class CVPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(140, 140, 140)
            self.cell(0, 5, 'Jahangir - Senior QA Engineer', align='R')
            self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

pdf = CVPDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

# ── Header ──────────────────────────────────────
pdf.set_fill_color(108, 92, 231)
pdf.rect(0, 0, 210, 45, 'F')
pdf.set_text_color(255, 255, 255)
pdf.set_font('Helvetica', 'B', 22)
pdf.set_y(8)
pdf.cell(0, 10, CV['name'], align='C')
pdf.set_font('Helvetica', '', 12)
pdf.cell(0, 8, CV['title'] + ' | ' + CV['status'], align='C')
pdf.set_font('Helvetica', '', 10)
pdf.cell(0, 7, CV['location'], align='C')

# ── Summary ─────────────────────────────────────
pdf.set_y(52)
pdf.set_fill_color(245, 245, 250)
pdf.set_text_color(50, 50, 50)
pdf.set_font('Helvetica', 'B', 13)
pdf.cell(0, 8, 'PROFESSIONAL SUMMARY', fill=True)
pdf.ln(10)
pdf.set_font('Helvetica', '', 10)
pdf.multi_cell(0, 5, CV['summary'])
pdf.ln(4)

# ── Experience ──────────────────────────────────
pdf.set_fill_color(245, 245, 250)
pdf.set_font('Helvetica', 'B', 13)
pdf.set_text_color(50, 50, 50)
pdf.cell(0, 8, 'EXPERIENCE', fill=True)
pdf.ln(10)

for exp in CV['experience']:
    period = exp['period'] if exp['period'] else ''
    title_line = f"{exp['role']} @ {exp['company']}"
    if period:
        title_line += f'  |  {period}'
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, title_line)
    pdf.ln(7)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(0, 5, exp['description'])
    if exp.get('keywords'):
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(108, 92, 231)
        pdf.cell(0, 5, 'Skills: ' + ', '.join(exp['keywords']))
        pdf.ln(4)
    pdf.ln(3)

# ── Technical Skills ────────────────────────────
pdf.set_fill_color(245, 245, 250)
pdf.set_font('Helvetica', 'B', 13)
pdf.set_text_color(50, 50, 50)
pdf.cell(0, 8, 'TECHNICAL SKILLS', fill=True)
pdf.ln(10)

for category, skills in CV['technical_skills'].items():
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, category)
    pdf.ln(6)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(0, 5, skills)
    pdf.ln(2)

# ── Certifications ──────────────────────────────
pdf.set_fill_color(245, 245, 250)
pdf.set_font('Helvetica', 'B', 13)
pdf.set_text_color(50, 50, 50)
pdf.cell(0, 8, 'CERTIFICATIONS', fill=True)
pdf.ln(10)

for cert in CV['certifications']:
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(70, 70, 70)
    year = f"({cert['year']})" if cert.get('year') else ''
    pdf.cell(0, 6, f"  - {cert['name']} {year}")
    pdf.ln(6)

# ── Languages ───────────────────────────────────
pdf.ln(3)
pdf.set_fill_color(245, 245, 250)
pdf.set_font('Helvetica', 'B', 13)
pdf.set_text_color(50, 50, 50)
pdf.cell(0, 8, 'LANGUAGES', fill=True)
pdf.ln(10)
pdf.set_font('Helvetica', '', 10)
pdf.set_text_color(70, 70, 70)
for lang in CV['languages']:
    pdf.cell(0, 6, f"  - {lang}")
    pdf.ln(6)

output_path = os.path.join(os.path.dirname(__file__), 'static', 'CV_Jahangir_English.pdf')
os.makedirs(os.path.dirname(output_path), exist_ok=True)
pdf.output(output_path)
print(f"CV generated: {output_path}")
