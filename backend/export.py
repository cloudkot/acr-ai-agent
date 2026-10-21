import json
import asyncio
import xml.etree.ElementTree as ET
from docx import Document
from docx.shared import RGBColor
from pptx import Presentation
from schemas import Framework
from logger import logger

# ==========================================
# [АРХИТЕКТУРА]: Синхронные генераторы (выполняются в отдельных потоках)
# ==========================================

def _export_to_docx_sync(framework: Framework, content: dict, filename: str, constraints_check: dict = None):
    doc = Document()
    doc.add_heading('ДОПОЛНИТЕЛЬНАЯ ПРОФЕССИОНАЛЬНАЯ ПРОГРАММА', 0)
    doc.add_paragraph(f"Тип: {framework.template_type}")
    doc.add_paragraph(f"Объем: {framework.total_hours} академических часов")
    
    if constraints_check and not constraints_check.get("constraints_ok", True):
        doc.add_heading('⚠ ВНИМАНИЕ: Предупреждения по ограничениям', level=1)
        p = doc.add_paragraph()
        p.runs[0].font.color.rgb = RGBColor(255, 0, 0)
        p.add_run("Нейросеть не до конца выполнила требования методиста:\n")
        for err in constraints_check.get("errors", []):
            doc.add_paragraph(err, style='List Bullet')

    doc.add_heading('1. Цель программы', level=1)
    doc.add_paragraph(framework.goal)
    if framework.prof_standard:
        doc.add_paragraph(f"Нормативная база: {framework.prof_standard}")

    doc.add_heading('2. Учебный план', level=1)
    table = doc.add_table(rows=1, cols=7)
    table.style = 'Table Grid'
    headers = ["№", "Наименование модуля", "Всего ч.", "ЛК", "ПР", "ЛБ", "СРС"]
    for i, text in enumerate(headers):
        table.rows[0].cells[i].text = text
        table.rows[0].cells[i].paragraphs[0].runs[0].bold = True

    for i, mod in enumerate(framework.modules, 1):
        row = table.add_row().cells
        row[0].text = str(i)
        row[1].text = mod.title
        row[2].text = str(mod.total_hours)
        row[3].text = str(mod.lectures)
        row[4].text = str(mod.practice)
        row[5].text = str(mod.labs)
        row[6].text = str(mod.srs)

    row = table.add_row().cells
    row[1].text = "Итоговая аттестация"
    row[2].text = str(framework.final_assessment_hours)
    for i in [0, 3, 4, 5, 6]: row[i].text = "-"

    row = table.add_row().cells
    row[1].text = "ИТОГО"
    row[1].paragraphs[0].runs[0].bold = True
    row[2].text = str(framework.total_hours)
    row[2].paragraphs[0].runs[0].bold = True

    if content.get("work_programs"):
        doc.add_heading('3. Рабочие программы модулей', level=1)
        for wp in content["work_programs"]:
            doc.add_heading(wp.get("module_title", "Модуль"), level=2)
            doc.add_paragraph(wp.get("description", ""))

    doc.add_heading('4. Тестовые материалы', level=1)
    for i, test in enumerate(content.get("tests", []), 1):
        doc.add_paragraph(f"Вопрос {i}: {test.get('question')}")
        for opt in test.get('options', []):
            prefix = "✅ " if opt == test.get('correct_answer') else "○ "
            doc.add_paragraph(f"{prefix}{opt}", style='List Bullet')
        doc.add_paragraph(f"Проверяемая компетенция: {test.get('related_competency', 'Не указана')}\n")

    doc.add_heading('5. Задания для семинаров', level=1)
    for i, sem in enumerate(content.get("seminars", []), 1):
        doc.add_heading(f"Семинар {i}: {sem.get('module_title', '')}", level=2)
        doc.add_paragraph(f"Задание: {sem.get('task')}")
        doc.add_paragraph(f"Критерии оценки: {sem.get('criteria')}")

    doc.add_heading('6. Планы лекций', level=1)
    for lec in content.get("lectures", []):
        doc.add_heading(lec.get('module_title', 'Модуль'), level=2)
        for thesis in lec.get('theses', []):
            doc.add_paragraph(thesis, style='List Bullet')

    if content.get("bibliography"):
        doc.add_heading('7. Список литературы', level=1)
        for book in content["bibliography"]:
            doc.add_paragraph(book, style='List Number')

    doc.save(filename)
    return filename

def _export_to_pptx_sync(framework: Framework, content: dict, filename: str, constraints_check: dict = None):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = f"Программа: {framework.goal[:50]}..."
    slide.placeholders[1].text = f"Объем: {framework.total_hours} ч.\nТип: {framework.template_type}"
    
    if constraints_check and not constraints_check.get("constraints_ok", True):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "⚠ Внимание: Отклонения от ТЗ"
        tf = slide.placeholders[1].text_frame
        tf.text = "При генерации были нарушены ограничения:"
        for err in constraints_check.get("errors", []):
            p = tf.add_paragraph()
            p.text = err
            p.level = 1

    slides_data = content.get("slides", [])
    if not slides_data and content.get("lectures"):
        slides_data = [{"slide_title": lec.get("module_title"), "module_title": lec.get("module_title"), "bullets": lec.get("theses", [])} for lec in content["lectures"]]

    for slide_info in slides_data:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = slide_info.get("slide_title", "Слайд")
        tf = slide.placeholders[1].text_frame
        tf.text = f"Модуль: {slide_info.get('module_title', '')}"
        for bullet in slide_info.get("bullets", []):
            p = tf.add_paragraph()
            p.text = bullet
            p.level = 1
            
    prs.save(filename)
    return filename

def _export_tests_to_lms_sync(tests_data: list, filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        for i, test in enumerate(tests_data, 1):
            question = test.get('question', f'Вопрос {i}')
            options = test.get('options', [])
            correct = test.get('correct_answer', '')
            f.write(f"::Вопрос {i}::{question} {{\n")
            for opt in options:
                if opt == correct: f.write(f"  ={opt}\n")
                else: f.write(f"  ~{opt}\n")
            f.write("}\n\n")
    return filename

def _export_tests_to_moodle_xml_sync(tests_data: list, filename: str):
    quiz = ET.Element("quiz")
    for i, test in enumerate(tests_data, 1):
        question = ET.SubElement(quiz, "question", type="multichoice")
        name = ET.SubElement(question, "name")
        ET.SubElement(name, "text").text = f"Вопрос {i}"
        
        q_text = ET.SubElement(question, "questiontext", format="html")
        ET.SubElement(q_text, "text").text = f"<p>{test.get('question', '')}</p>"
        
        for opt in test.get('options', []):
            fraction = "100" if opt == test.get('correct_answer') else "0"
            answer = ET.SubElement(question, "answer", fraction=fraction, format="html")
            ET.SubElement(answer, "text").text = f"<p>{opt}</p>"
            
    tree = ET.ElementTree(quiz)
    ET.indent(tree, space="  ")
    tree.write(filename, encoding="utf-8", xml_declaration=True)
    return filename

def _export_to_json_sync(framework: Framework, content: dict, filename: str, constraints_check: dict = None):
    data = {
        "framework": framework.model_dump(),
        "content": content,
        "constraints_check": constraints_check
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filename

# ==========================================
# [АРХИТЕКТУРА]: Асинхронные обертки
# ==========================================

async def export_to_docx(framework: Framework, content: dict, filename: str, constraints_check: dict = None):
    """[ФИКС]: Запуск генерации Word в отдельном потоке."""
    return await asyncio.to_thread(_export_to_docx_sync, framework, content, filename, constraints_check)

async def export_to_pptx(framework: Framework, content: dict, filename: str, constraints_check: dict = None):
    """[ФИКС]: Запуск генерации PPTX в отдельном потоке."""
    return await asyncio.to_thread(_export_to_pptx_sync, framework, content, filename, constraints_check)

async def export_tests_to_lms(tests_data: list, filename: str):
    return await asyncio.to_thread(_export_tests_to_lms_sync, tests_data, filename)

async def export_tests_to_moodle_xml(tests_data: list, filename: str):
    return await asyncio.to_thread(_export_tests_to_moodle_xml_sync, tests_data, filename)

async def export_to_json(framework: Framework, content: dict, filename: str, constraints_check: dict = None):
    return await asyncio.to_thread(_export_to_json_sync, framework, content, filename, constraints_check)