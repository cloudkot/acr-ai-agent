from docx import Document
from pptx import Presentation
from schemas import Framework
import json

def export_to_docx(framework: Framework, content: dict, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка в .docx по шаблону АЦР.
    """
    doc = Document()
    doc.add_heading('Образовательная программа (АЦР)', 0)
    
    doc.add_heading('1. Цель программы', level=1)
    doc.add_paragraph(framework.goal)
    
    doc.add_heading('2. Учебный план', level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Модуль'
    hdr_cells[1].text = 'Часы'
    
    for mod in framework.modules:
        row_cells = table.add_row().cells
        row_cells[0].text = mod.title
        row_cells[1].text = str(mod.hours)
        
    doc.add_heading('3. Тестовые материалы', level=1)
    doc.add_paragraph(json.dumps(content.get('tests', []), ensure_ascii=False, indent=2))
    
    doc.add_heading('4. Задания для семинаров', level=1)
    doc.add_paragraph(json.dumps(content.get('seminars', {}), ensure_ascii=False, indent=2))
    
    doc.add_heading('5. Планы лекций', level=1)
    doc.add_paragraph(content.get('lectures', ''))
    
    doc.save(filename)
    return filename

def export_to_pptx(framework: Framework, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Планы лекций и слайды в .pptx.
    """
    prs = Presentation()
    
    # Титульный слайд
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Образовательная программа"
    slide.placeholders[1].text = framework.goal
    
    # Слайды для модулей
    for mod in framework.modules:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = mod.title
        slide.placeholders[1].text = f"Объем: {mod.hours} ч."
        
    prs.save(filename)
    return filename

def export_tests_to_lms(tests_data: list, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка тестов в формат LMS (GIFT).
    """
    with open(filename, 'w', encoding='utf-8') as f:
        for test in tests_data:
            f.write(f"::{test.get('question')}::\n")
            f.write(f"{test.get('question')} {{\n")
            for opt in test.get('options', []):
                if opt == test.get('correct_answer'):
                    f.write(f"  ={opt}\n")
                else:
                    f.write(f"  ~{opt}\n")
            f.write("}\n\n")
    return filename