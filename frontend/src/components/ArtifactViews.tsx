import { useState } from 'react';
import { Edit3, CheckCircle2 } from 'lucide-react';

// 1. Карта компетенций
export const CompetenciesView = ({ data }: { data: any[] }) => {
  if (!data || data.length === 0) return <div className="text-gray-400 text-center py-10">Нет данных</div>;
  return (
    <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-100 font-semibold text-gray-700">
          <tr>
            <th className="p-4 border-b">Компетенция</th>
            <th className="p-4 border-b">Знания</th>
            <th className="p-4 border-b">Умения</th>
            <th className="p-4 border-b">Навыки</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, idx) => (
            <tr key={idx} className="hover:bg-gray-50 transition-colors">
              <td className="p-4 border-b font-medium text-blue-900">{item.name}</td>
              <td className="p-4 border-b text-gray-600">{item.knowledge?.join(', ')}</td>
              <td className="p-4 border-b text-gray-600">{item.skills?.join(', ')}</td>
              <td className="p-4 border-b text-gray-600">{item.abilities?.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// 2. Учебный план
export const PlanView = ({ data }: { data: any[] }) => {
  if (!data || data.length === 0) return <div className="text-gray-400 text-center py-10">Нет данных</div>;
  return (
    <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-100 font-semibold text-gray-700">
          <tr>
            <th className="p-4 border-b">Модуль</th>
            <th className="p-4 border-b text-center">Лекции (ч)</th>
            <th className="p-4 border-b text-center">Семинары (ч)</th>
            <th className="p-4 border-b text-center">Самостоятельная работа (ч)</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, idx) => (
            <tr key={idx} className="hover:bg-gray-50">
              <td className="p-4 border-b font-medium">{item.module}</td>
              <td className="p-4 border-b text-center">{item.lectures}</td>
              <td className="p-4 border-b text-center">{item.seminars}</td>
              <td className="p-4 border-b text-center">{item.self_study}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// 3. Тесты (с точечной доработкой)
export const TestsView = ({ data, onRefine }: { data: any[], onRefine: (id: string, inst: string) => void }) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [instruction, setInstruction] = useState('');

  if (!data || data.length === 0) return <div className="text-gray-400 text-center py-10">Нет данных</div>;

  return (
    <div className="space-y-4">
      {data.map((test, idx) => (
        <div key={idx} className="p-5 border rounded-lg bg-white shadow-sm relative group">
          <div className="font-semibold mb-3 text-gray-800">{idx + 1}. {test.question}</div>
          <ul className="space-y-1 text-sm text-gray-600 mb-3">
            {test.options?.map((opt: string, i: number) => (
              <li key={i} className={`flex items-center gap-2 ${opt === test.correct_answer ? "text-green-600 font-medium" : ""}`}>
                {opt === test.correct_answer ? <CheckCircle2 className="w-4 h-4" /> : <div className="w-4 h-4" />}
                {String.fromCharCode(65 + i)}) {opt}
              </li>
            ))}
          </ul>
          <div className="text-xs text-gray-400 bg-gray-50 inline-block px-2 py-1 rounded">Ключ: {test.correct_answer}</div>
          
          {/* Кнопка редактирования */}
          <button 
            onClick={() => setEditingId(editingId === idx.toString() ? null : idx.toString())}
            className="absolute top-5 right-5 opacity-0 group-hover:opacity-100 transition-opacity p-2 text-gray-400 hover:text-blue-600 bg-gray-50 hover:bg-blue-50 rounded-full"
            title="Точечная доработка"
          >
            <Edit3 className="w-4 h-4" />
          </button>

          {/* Инлайн-редактор */}
          {editingId === idx.toString() && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-100">
              <div className="text-xs font-semibold text-blue-800 mb-2">Что изменить в этом вопросе?</div>
              <input 
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Например: Сделай вопрос сложнее или добавь вариант 'Все вышеперечисленное'"
                className="w-full text-sm p-2 border rounded mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-2">
                <button 
                  onClick={() => { onRefine(idx.toString(), instruction); setEditingId(null); setInstruction(''); }}
                  className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 transition-colors"
                >
                  Применить правку
                </button>
                <button 
                  onClick={() => setEditingId(null)}
                  className="text-gray-500 px-4 py-2 rounded text-sm hover:bg-gray-200 transition-colors"
                >
                  Отмена
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

// 4. Семинары (заглушка для полноты)
export const SeminarsView = ({ data }: { data: any[] }) => {
  if (!data || data.length === 0) return <div className="text-gray-400 text-center py-10">Нет данных</div>;
  return (
    <div className="space-y-4">
      {data.map((item, idx) => (
        <div key={idx} className="p-4 border rounded-lg bg-white shadow-sm">
          <div className="font-semibold">{item.title}</div>
          <div className="text-sm text-gray-500 mt-1">Критерии: {item.criteria}</div>
        </div>
      ))}
    </div>
  );
};

// 5. Слайды (заглушка для полноты)
export const SlidesView = ({ data }: { data: any[] }) => {
  if (!data || data.length === 0) return <div className="text-gray-400 text-center py-10">Нет данных</div>;
  return (
    <div className="grid grid-cols-2 gap-4">
      {data.map((slide, idx) => (
        <div key={idx} className="p-6 border rounded-lg bg-white shadow-sm aspect-video flex flex-col justify-center items-center text-center">
          <div className="font-bold text-lg mb-2">{slide.title}</div>
          <div className="text-sm text-gray-500">{slide.content}</div>
        </div>
      ))}
    </div>
  );
};
