from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from schemas import Framework
import json

def export_to_docx(framework: Framework, content: dict, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка программы в .docx по шаблону АЦР.
    Включает цель, учебный план, рабочие программы, тесты, семинары, лекции и библиографию.
    """
    doc = Document()
    doc.add_heading('Образовательная программа (АЦР)', 0)
    
    # 1. Цель
    doc.add_heading('1. Цель программы', level=1)
    doc.add_paragraph(framework.goal)
    
    # 2. Учебный план
    doc.add_heading('2. Учебный план', level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.rows[0].cells[0].text = "Название модуля"
    table.rows[0].cells[1].text = "Часы"
    for mod in framework.modules:
        row = table.add_row().cells
        row[0].text = mod.title
        row[1].text = str(mod.hours)
    doc.add_paragraph(f"Итого часов: {framework.total_hours}")

    # 3. Рабочие программы модулей
    if content.get("work_programs"):
        doc.add_heading('3. Рабочие программы модулей', level=1)
        for wp in content["work_programs"]:
            doc.add_heading(wp.get("module_title", "Модуль"), level=2)
            doc.add_paragraph(wp.get("description", ""))

    # 4. Тесты
    doc.add_heading('4. Тестовые материалы', level=1)
    for i, test in enumerate(content.get("tests", []), 1):
        doc.add_paragraph(f"Вопрос {i}: {test.get('question')}")
        for opt in test.get('options', []):
            prefix = "✅ " if opt == test.get('correct_answer') else "○ "
            doc.add_paragraph(f"{prefix}{opt}", style='List Bullet')
        doc.add_paragraph(f"Проверяемая компетенция: {test.get('related_competency', 'Не указана')}\n")

    # 5. Семинары
    doc.add_heading('5. Задания для семинаров', level=1)
    sem = content.get("seminars", {})
    doc.add_paragraph(f"Задание: {sem.get('task')}")
    doc.add_paragraph(f"Критерии оценки: {sem.get('criteria')}")

    # 6. Лекции
    doc.add_heading('6. Планы лекций', level=1)
    for lec in content.get("lectures", []):
        doc.add_heading(lec.get('module_title', 'Модуль'), level=2)
        for thesis in lec.get('theses', []):
            doc.add_paragraph(thesis, style='List Bullet')

    # 7. Библиография
    if content.get("bibliography"):
        doc.add_heading('7. Список литературы', level=1)
        for book in content["bibliography"]:
            doc.add_paragraph(book, style='List Number')

    doc.save(filename)
    return filename

def export_to_pptx(framework: Framework, content: dict, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Планы лекций и слайды в .pptx.
    """
    prs = Presentation()
    
    # Титульный слайд
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Образовательная программа"
    slide.placeholders[1].text = framework.goal
    
    # Слайды для модулей (используем тезисы лекций)
    lectures_map = {lec.get('module_title'): lec.get('theses', []) for lec in content.get("lectures", [])}
    
    for mod in framework.modules:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = mod.title
        tf = slide.placeholders[1].text_frame
        tf.text = f"Объем: {mod.hours} академических часов"
        
        theses = lectures_map.get(mod.title, ["Тезисы лекций не сгенерированы"])
        for thesis in theses:
            p = tf.add_paragraph()
            p.text = thesis
            p.level = 1
            
    prs.save(filename)
    return filename

def export_tests_to_lms(tests_data: list, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка тестов в формат LMS (GIFT).
    Строгое соблюдение синтаксиса Moodle GIFT.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        for i, test in enumerate(tests_data, 1):
            question = test.get('question', 'Вопрос')
            options = test.get('options', [])
            correct = test.get('correct_answer', '')
            
            # Заголовок вопроса в GIFT (::Название::)
            f.write(f"::Вопрос {i}::{question} {{\n")
            for opt in options:
                if opt == correct:
                    f.write(f"  ={opt}\n") # Правильный ответ
                else:
                    f.write(f"  ~{opt}\n") # Неправильный ответ
            f.write("}\n\n")
    return filename

def export_to_json(framework: Framework, content: dict, filename: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Сохранение полного комплекта данных в JSON.
    """
    data = {
        "framework": framework.model_dump(),
        "content": content
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filename