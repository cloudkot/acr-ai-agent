from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from schemas import Framework

def export_to_docx(framework: Framework, content: dict, filename: str = "program.docx"):
    """[ТРЕБОВАНИЕ КЕЙСА]: Выгрузка программы в .docx по шаблону АЦР."""
    doc = Document()
    doc.add_heading('Образовательная программа (АЦР)', 0)
    
    doc.add_heading('1. Цель программы', level=1)
    doc.add_paragraph(framework.goal)
    
    doc.add_heading('2. Карта компетенций', level=1)
    for comp in framework.competencies:
        doc.add_heading(comp.name, level=2)
        doc.add_paragraph(f"Знания: {', '.join(comp.knowledge)}")
        doc.add_paragraph(f"Умения: {', '.join(comp.skills)}")
        
    doc.add_heading('3. Учебный план', level=1)
    for mod in framework.modules:
        doc.add_paragraph(f"{mod.title} — {mod.hours} ч.")
    doc.add_paragraph(f"Итого: {framework.total_hours} ч.")
    
    doc.add_heading('4. Тестовые материалы', level=1)
    doc.add_paragraph(content.get("tests", ""))
    
    doc.add_heading('5. Задания для семинаров', level=1)
    doc.add_paragraph(content.get("seminars", ""))
    
    doc.save(filename)
    return filename

# [ТРЕБОВАНИЕ КЕЙСА]: Планы лекций и слайды в .pptx
def export_to_pptx(framework: Framework, filename: str = "presentation.pptx"):
    """Генерация презентации по модулям программы."""
    prs = Presentation()
    
    # Титульный слайд
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = "Образовательная программа"
    subtitle.text = framework.goal
    
    # Слайд для каждого модуля
    bullet_slide_layout = prs.slide_layouts[1]
    for mod in framework.modules:
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        
        title_shape.text = mod.title
        
        tf = body_shape.text_frame
        tf.text = f"Объем: {mod.hours} часов"
        p = tf.add_paragraph()
        p.text = "Ключевые компетенции:"
        p.level = 1
        for comp in framework.competencies[:2]: # Берем первые 2 для примера
            p = tf.add_paragraph()
            p.text = comp.name
            p.level = 2
            
    prs.save(filename)
    return filename