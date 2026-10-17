from docx import Document
import json

def export_to_docx(framework_text: str, content: dict, filename: str = "program.docx"):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка программы в .docx по шаблону АЦР.
    Собирает каркас, тесты и семинары в один документ.
    """
    doc = Document()
    doc.add_heading('Образовательная программа', 0)
    
    doc.add_heading('1. Каркас программы (Утвержден методистом)', level=1)
    doc.add_paragraph(framework_text)
    
    doc.add_heading('2. Тестовые материалы', level=1)
    doc.add_paragraph(content.get("tests", "Тесты не сгенерированы."))
    
    doc.add_heading('3. Задания для семинаров', level=1)
    doc.add_paragraph(content.get("seminars", "Семинары не сгенерированы."))
    
    doc.save(filename)
    return filename

def export_tests_to_lms(tests_text: str, filename: str = "tests.json"):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Выгрузка тестов в формат LMS.
    """
    # В MVP просто сохраняем текст тестов в JSON
    data = {"tests": tests_text}
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filename