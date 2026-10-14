import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface GenerateRequest {
  prompt: string;
  hours: number;
  direction: string;
}

export interface Artifacts {
  competencies?: any[];
  plan?: any[];
  tests?: any[];
  seminars?: any[];
  slides?: any[];
  report?: any;
}

// Флаг для тестирования без бэкенда
const USE_MOCK = true; 

export const api = {
  startGeneration: async (data: GenerateRequest, files: File[]) => {
    if (USE_MOCK) {
      return new Promise(resolve => setTimeout(() => resolve({ task_id: 'mock-123' }), 1000));
    }
    const formData = new FormData();
    formData.append('prompt', data.prompt);
    formData.append('hours', data.hours.toString());
    formData.append('direction', data.direction);
    files.forEach((file) => formData.append('files', file));

    const response = await axios.post(`${API_URL}/api/generate`, formData);
    return response.data;
  },

  getStatus: async (taskId: string) => {
    if (USE_MOCK) {
      // Имитация пошаговой генерации
      const steps = ['Анализ референсов', 'Генерация карты компетенций', 'Создание учебного плана', 'Генерация тестов', 'Создание слайдов'];
      return new Promise(resolve => {
        setTimeout(() => {
          resolve({
            status: 'completed',
            current_step: 'Готово',
            artifacts: {
              competencies: [
                { name: 'Основы Python', knowledge: ['Синтаксис', 'Типы данных'], skills: ['Писать скрипты'], abilities: ['Читать код'] },
                { name: 'Работа с API', knowledge: ['REST', 'JSON'], skills: ['Отправлять запросы'], abilities: ['Интегрировать сервисы'] },
              ],
              plan: [
                { module: 'Введение', lectures: 4, seminars: 4, self_study: 8 },
                { module: 'Основы', lectures: 8, seminars: 8, self_study: 16 },
              ],
              tests: [
                { question: 'Что такое Python?', options: ['Змея', 'Язык программирования', 'Игра'], correct_answer: 'Язык программирования' },
                { question: 'Какой оператор используется для возведения в степень?', options: ['^', '**', '//'], correct_answer: '**' },
              ],
              seminars: [
                { title: 'Установка окружения', criteria: 'Успешный запуск скрипта' }
              ],
              slides: [
                { title: 'Введение в Python', content: 'История языка, области применения' }
              ]
            }
          });
        }, 3000);
      });
    }
    const response = await axios.get(`${API_URL}/api/status/${taskId}`);
    return response.data;
  },

  refineItem: async (taskId: string, artifactType: string, itemId: string, instruction: string) => {
    if (USE_MOCK) {
      return new Promise(resolve => setTimeout(() => resolve({ success: true }), 1000));
    }
    const response = await axios.post(`${API_URL}/api/refine`, {
      task_id: taskId,
      artifact_type: artifactType,
      item_id: itemId,
      instruction,
    });
    return response.data;
  },

  exportDocx: async (taskId: string) => {
    if (USE_MOCK) {
      alert('В реальном приложении здесь начнется скачивание DOCX');
      return;
    }
    const response = await axios.get(`${API_URL}/api/export/docx/${taskId}`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `program_${taskId}.docx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },
};