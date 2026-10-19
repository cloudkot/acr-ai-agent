// frontend/src/api.ts

const BASE_URL = '/api';

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

export interface ValidationReport {
  hours_match: boolean;
  calculated_total: number;
  expected_total: number;
  competency_coverage: boolean;
  total_competencies: number;
}

export interface GenerateResponse {
  session_id: string;
  status: string;
  validation_report?: ValidationReport;
  framework: Framework;
}

export interface ContentData {
  tests?: {
    questions?: Array<{
      question: string;
      options: string[];
      correct_answer: string;
      related_competency?: string;
    }>;
  };
  seminars?: {
    task?: string;
    criteria?: string;
  };
  lectures?: {
    modules_plan?: Array<{
      module_title: string;
      theses: string[];
    }>;
  };
}

export interface ContentResponse {
  session_id: string;
  status: string;
  content: ContentData;
  validation_report?: ValidationReport;
}

// 1. Генерация каркаса
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
export async function reviseFramework(sessionId: string, instruction: string): Promise<GenerateResponse> {
  const res = await fetch(`${BASE_URL}/revise/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction }),
  });
  
  if (!res.ok) {
    let errorMsg = 'Ошибка доработки каркаса';
    try {
      const errData = await res.json();
      errorMsg = errData.detail || errData.message || errorMsg;
    } catch (e) {}
    throw new Error(errorMsg);
  }
  return res.json();
}

// 3. Утверждение каркаса
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

// 4. Скачивание файлов
export async function downloadFile(sessionId: string, type: 'docx' | 'pptx' | 'lms') {
  const res = await fetch(`${BASE_URL}/export-${type}/${sessionId}`, { method: 'POST' });
  if (!res.ok) throw new Error('Ошибка экспорта файла');
  
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  
  // GIFT (LMS) должен быть .txt
  let ext = type as string;
  if (type === 'lms') {
    ext = 'txt'; 
  }

  a.download = `result_${sessionId.slice(0, 8)}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}