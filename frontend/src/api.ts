// frontend/src/api.ts

const BASE_URL = 'https://tochka-sborki-2026-team-058.hub.gigaschool.ru:8000/api';
// Для локальной разработки: const BASE_URL = 'http://localhost:8000/api';

export interface Competency {
  name: string;
  knowledge: string[];
  skills: string[];
}

export interface Module {
  title: string;
  hours: number;
}

export interface Framework {
  goal: string;
  competencies: Competency[];
  modules: Module[];
  total_hours: number;
}

export interface GenerateResponse {
  session_id: string;
  status: string;
  framework: Framework;
}

export interface ContentResponse {
  session_id: string;
  status: string;
  content: {
    tests: string;
    seminars: string;
    lectures: string;
  };
  validation_report?: any; // Поле для отчета (строка или объект)
}

// 1. Генерация каркаса с обработкой ошибок
export async function generateFramework(topic: string, hours: number): Promise<GenerateResponse> {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, hours }),
  });
  
  if (!res.ok) {
    let errorMsg = 'Не удалось сгенерировать каркас. Попробуйте позже.';
    try {
      const errData = await res.json();
      errorMsg = errData.detail || errData.message || errorMsg;
    } catch (e) {}
    throw new Error(errorMsg);
  }
  return res.json();
}

// 2. Точечная доработка
export async function reviseFramework(sessionId: string, instruction: string) {
  const res = await fetch(`${BASE_URL}/revise/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction }),
  });
  if (!res.ok) throw new Error('Ошибка доработки каркаса');
  return res.json();
}

// 3. Утверждение каркаса с обработкой ошибок
export async function approveFramework(sessionId: string): Promise<ContentResponse> {
  const res = await fetch(`${BASE_URL}/approve/${sessionId}`, { method: 'POST' });
  
  if (!res.ok) {
    let errorMsg = 'Не удалось сгенерировать контент. Проверьте соединение.';
    try {
      const errData = await res.json();
      errorMsg = errData.detail || errData.message || errorMsg;
    } catch (e) {}
    throw new Error(errorMsg);
  }
  return res.json();
}

// 4. Скачивание файлов (ИСПРАВЛЕНИЕ ОШИБКИ С CSV/GIFT)
export async function downloadFile(sessionId: string, type: 'docx' | 'pptx' | 'lms') {
  const res = await fetch(`${BASE_URL}/export-${type}/${sessionId}`, { method: 'POST' });
  if (!res.ok) throw new Error('Ошибка экспорта файла');
  
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  
  // ИСПРАВЛЕНО: GIFT (LMS) должен быть .txt, а не .csv!
  let ext = type as string;
  if (type === 'lms') {
    ext = 'txt'; 
  }

  a.download = `result_${sessionId.slice(0, 8)}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}