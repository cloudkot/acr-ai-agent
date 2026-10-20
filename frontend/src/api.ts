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
  deep_coverage?: {
    coverage_ok: boolean;
    tested_count: number;
    total_competencies: number;
    uncovered: string[];
  };
  sources_check?: {
    warnings: string[];
  };
}

export interface GenerateResponse {
  session_id: string;
  status: string;
  validation_report?: ValidationReport;
  framework: Framework;
}

export interface Seminar {
  task: string;
  criteria: string;
}

export interface WorkProgram {
  module_title: string;
  // Бэкенд может присылать разные поля, поэтому делаем опциональными
  description?: string;
  topics?: string[];
  hours?: number;
}

export interface BibliographyItem {
  title: string;
  author?: string;
  year?: string;
  url?: string;
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
  // ИСПРАВЛЕНО: теперь массив семинаров
  seminars?: Seminar[];
  lectures?: {
    modules_plan?: Array<{
      module_title: string;
      theses: string[];
    }>;
  };
  // НОВЫЕ АРТЕФАКТЫ
  work_programs?: WorkProgram[];
  bibliography?: BibliographyItem[];
}

export interface ContentResponse {
  session_id: string;
  status: string;
  content: ContentData;
  validation_report?: ValidationReport;
}

// 0. Загрузка референса
export async function uploadReference(file: File): Promise<{ full_text: string; filename: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_URL}/upload-reference`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Ошибка загрузки референса');
  return res.json();
}

// 1. Генерация каркаса
export async function generateFramework(
  topic: string, 
  hours: number, 
  templateType: string = 'auto', 
  referenceText?: string
): Promise<GenerateResponse> {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      topic, 
      hours, 
      template_type: templateType, 
      reference_text: referenceText || undefined 
    }),
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

// 4. Скачивание файлов (GET)
export function downloadFile(sessionId: string, type: 'docx' | 'pptx' | 'lms' | 'json') {
  window.location.href = `${BASE_URL}/export-${type}/${sessionId}`;
}