from docx import Document
from pptx import Presentation
from schemas import Framework
import json

def export_to_docx(framework: Framework, content: dict, filename: str):
    doc = Document()
    doc.add_heading('Образовательная программа (АЦР)', 0)
    doc.add_paragraph(f"Цель: {framework.goal}")
    
    # Учебный план
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.rows[0].cells[0].text = "Модуль"
    table.rows[0].cells[1].text = "Часы"
    for mod in framework.modules:
        row = table.add_row().cells
        row[0].text = mod.title
        row[1].text = str(mod.hours)
        
    doc.add_paragraph(f"\nТесты:\n{json.dumps(content.get('tests', []), ensure_ascii=False, indent=2)}")
    doc.add_paragraph(f"\nСеминары:\n{json.dumps(content.get('seminars', {}), ensure_ascii=False, indent=2)}")
    
    # Структурированные лекции
    doc.add_paragraph("\nПланы лекций:")
    for lec in content.get('lectures', []):
        doc.add_paragraph(f"Модуль: {lec.get('module_title')}", style='List Bullet')
        for thesis in lec.get('theses', []):
            doc.add_paragraph(thesis, style='List Bullet 2')
            
    doc.save(filename)
    return filename

def export_to_pptx(framework: Framework, content: dict, filename: str):
    prs = Presentation()
    
    # Титул
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Образовательная программа"
    slide.placeholders[1].text = framework.goal
    
    # Слайды из лекций
    for lec in content.get('lectures', []):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = lec.get('module_title', 'Модуль')
        tf = slide.placeholders[1].text_frame
        tf.text = "Ключевые тезисы:"
        for thesis in lec.get('theses', []):
            p = tf.add_paragraph()
            p.text = thesis
            p.level = 1
            
    prs.save(filename)
    return filename

def export_tests_to_lms(tests_data: list, filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        for test in tests_data:
            f.write(f"::{test.get('question')}::\n{test.get('question')} {{\n")
            for opt in test.get('options', []):
                sign = "=" if opt == test.get('correct_answer') else "~"
                f.write(f"  {sign}{opt}\n")
            f.write("}\n\n")