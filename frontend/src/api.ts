// frontend/src/api.ts

const BASE_URL = 'http://localhost:8000/api'; // или публичный URL ВМ

// Типы, которые точно совпадают с Pydantic-схемами на бэкенде
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
  message?: string;
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
}

// 1. Проверка связи с LLM
export async function testLLM() {
  const res = await fetch(`${BASE_URL}/test-llm`);
  return res.json();
}

// 2. Генерация каркаса (вызывать, когда методист ввел тему и часы)
export async function generateFramework(topic: string, hours: number): Promise<GenerateResponse> {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, hours }),
  });
  if (!res.ok) throw new Error('Ошибка генерации каркаса');
  return res.json();
}

// 3. Утверждение каркаса (Human-in-the-loop)
export async function approveFramework(sessionId: string): Promise<ContentResponse> {
  const res = await fetch(`${BASE_URL}/approve/${sessionId}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Ошибка утверждения');
  return res.json();
}

// 4. Экспорт в Word (возвращает файл, его нужно скачать)
export async function exportToDocx(sessionId: string) {
  const res = await fetch(`${BASE_URL}/export/${sessionId}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Ошибка экспорта');
  
  // Скачивание файла
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `program_${sessionId.slice(0, 8)}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}