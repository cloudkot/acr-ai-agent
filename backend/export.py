from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from schemas import Framework
import csv
import json

def export_to_docx(framework: Framework, content: dict, filename: str = "program.docx"):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка программы в .docx по шаблону АЦР.
    """
    doc = Document()
    doc.add_heading('Образовательная программа (АЦР)', 0)
    
    # Цель
    doc.add_heading('1. Цель программы', level=1)
    doc.add_paragraph(framework.goal)
    
    # Компетенции (Таблица)
    doc.add_heading('2. Карта компетенций', level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Компетенция'
    hdr_cells[1].text = 'Знания'
    hdr_cells[2].text = 'Умения и навыки'
    
    for comp in framework.competencies:
        row_cells = table.add_row().cells
        row_cells[0].text = comp.name
        row_cells[1].text = ', '.join(comp.knowledge)
        row_cells[2].text = ', '.join(comp.skills)
        
    # Учебный план
    doc.add_heading('3. Учебный план', level=1)
    for mod in framework.modules:
        doc.add_paragraph(f"Модуль: {mod.title} — {mod.hours} ч.", style='List Bullet')
    doc.add_paragraph(f"Итого часов: {framework.total_hours}")

    # Тесты
    doc.add_heading('4. Тестовые материалы', level=1)
    for i, test in enumerate(content.get("tests", []), 1):
        doc.add_paragraph(f"Вопрос {i}: {test.get('question')}")
        for opt in test.get('options', []):
            doc.add_paragraph(f"- {opt}", style='List Bullet')
        doc.add_paragraph(f"Правильный ответ: {test.get('correct_answer')}")
        doc.add_paragraph(f"Проверяемая компетенция: {test.get('related_competency')}\n")

    # Семинары
    doc.add_heading('5. Задания для семинаров', level=1)
    sem = content.get("seminars", {})
    doc.add_paragraph(f"Задание: {sem.get('task')}")
    doc.add_paragraph(f"Критерии оценки: {sem.get('criteria')}")

    # Лекции
    doc.add_heading('6. Планы лекций', level=1)
    doc.add_paragraph(content.get("lectures", ""))
    
    doc.save(filename)
    return filename

def export_to_pptx(framework: Framework, filename: str = "presentation.pptx"):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Слайды для лекций в .pptx.
    """
    prs = Presentation()
    
    # Титульный слайд
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = "Образовательная программа"
    title_slide.placeholders[1].text = framework.goal
    
    # Слайд с компетенциями
    comp_slide = prs.slides.add_slide(prs.slide_layouts[1])
    comp_slide.shapes.title.text = "Карта компетенций"
    tf = comp_slide.placeholders[1].text_frame
    for comp in framework.competencies:
        p = tf.add_paragraph()
        p.text = comp.name
        p.level = 0
        
    # Слайд для каждого модуля
    for mod in framework.modules:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = mod.title
        tf = slide.placeholders[1].text_frame
        tf.text = f"Объем: {mod.hours} академических часов"
        p = tf.add_paragraph()
        p.text = "Ключевые темы модуля:"
        p.level = 1
        # Добавляем заглушки для тем, чтобы слайд не был пустым
        for i in range(1, 4):
            p = tf.add_paragraph()
            p.text = f"Тема {i} (будет сгенерирована в полной версии)"
            p.level = 2
            
    prs.save(filename)
    return filename

def export_tests_to_lms(tests_data: list, filename: str = "tests_gift.txt"):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка тестов в формат LMS (GIFT).
    GIFT — это стандартный текстовый формат для Moodle.
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