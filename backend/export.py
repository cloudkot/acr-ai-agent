from docx import Document
from pptx import Presentation
from schemas import Framework
import json

def export_to_docx(framework: Framework, content: dict, filename: str):
    doc = Document()
    doc.add_heading('Образовательная программа', 0)
    doc.add_paragraph(f"Цель: {framework.goal}")
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.rows[0].cells[0].text = "Модуль"
    table.rows[0].cells[1].text = "Часы"
    for mod in framework.modules:
        table.add_row().cells[0].text = mod.title
        table.add_row().cells[1].text = str(mod.hours)
        
    doc.add_paragraph(f"\nТесты:\n{json.dumps(content.get('tests', []), ensure_ascii=False, indent=2)}")
    doc.add_paragraph(f"\nСеминары:\n{json.dumps(content.get('seminars', {}), ensure_ascii=False, indent=2)}")
    doc.add_paragraph(f"\nЛекции:\n{content.get('lectures', '')}")
    doc.save(filename)

def export_to_pptx(framework: Framework, filename: str):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Образовательная программа"
    slide.placeholders[1].text = framework.goal
    for mod in framework.modules:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = mod.title
        slide.placeholders[1].text = f"Объем: {mod.hours} ч."
    prs.save(filename)

def export_tests_to_lms(tests_data: list, filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        for test in tests_data:
            f.write(f"::{test.get('question')}::\n{test.get('question')} {{\n")
            for opt in test.get('options', []):
                sign = "=" if opt == test.get('correct_answer') else "~"
                f.write(f"  {sign}{opt}\n")
            f.write("}\n\n")