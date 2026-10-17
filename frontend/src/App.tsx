import { useState } from 'react';
import { Loader2, ArrowRight, CheckCircle2, Download, FileText, BookOpen, GraduationCap, RotateCcw } from 'lucide-react';
import { 
  generateFramework, 
  approveFramework, 
  exportToDocx,
  type Framework,
  type ContentResponse 
} from './api';

type Screen = 'input' | 'framework' | 'result';

function App() {
  const [screen, setScreen] = useState<Screen>('input');
  const [topic, setTopic] = useState('');
  const [hours, setHours] = useState<number>(72);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [sessionId, setSessionId] = useState<string>('');
  const [framework, setFramework] = useState<Framework | null>(null);
  const [content, setContent] = useState<ContentResponse['content'] | null>(null);

  // --- Экран 1: Генерация каркаса ---
  const handleGenerate = async () => {
    if (!topic.trim() || hours <= 0) {
      setError('Введите тему и количество часов');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await generateFramework(topic, hours);
      setSessionId(res.session_id);
      setFramework(res.framework);
      setScreen('framework');
    } catch (e) {
      setError('Не удалось сгенерировать каркас. Проверьте бэкенд.');
    } finally {
      setLoading(false);
    }
  };

  // --- Экран 2: Утверждение каркаса ---
  const handleApprove = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await approveFramework(sessionId);
      setContent(res.content);
      setScreen('result');
    } catch (e) {
      setError('Не удалось сгенерировать контент.');
    } finally {
      setLoading(false);
    }
  };

  // --- Экран 3: Экспорт ---
  const handleExport = async () => {
    try {
      await exportToDocx(sessionId);
    } catch (e) {
      setError('Не удалось скачать файл.');
    }
  };

  // --- Перезапуск ---
  const handleRestart = () => {
    setScreen('input');
    setTopic('');
    setHours(72);
    setSessionId('');
    setFramework(null);
    setContent(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 text-gray-900">
      {/* Шапка с прогрессом */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold">
                AI
              </div>
              <div>
                <div className="font-bold text-sm">ACR AI Agent</div>
                <div className="text-xs text-gray-500">Генератор программ</div>
              </div>
            </div>
            {screen !== 'input' && (
              <button onClick={handleRestart} className="text-xs text-gray-500 hover:text-blue-600 flex items-center gap-1">
                <RotateCcw className="w-3 h-3" /> Начать заново
              </button>
            )}
          </div>

          {/* Stepper */}
          <div className="flex items-center mt-4 text-xs">
            <Step num={1} label="Ввод" active={screen === 'input'} done={screen !== 'input'} />
            <div className={`flex-1 h-0.5 mx-2 ${screen !== 'input' ? 'bg-green-500' : 'bg-gray-200'}`} />
            <Step num={2} label="Каркас" active={screen === 'framework'} done={screen === 'result'} />
            <div className={`flex-1 h-0.5 mx-2 ${screen === 'result' ? 'bg-green-500' : 'bg-gray-200'}`} />
            <Step num={3} label="Результат" active={screen === 'result'} done={false} />
          </div>
        </div>
      </header>

      {/* Ошибка */}
      {error && (
        <div className="max-w-4xl mx-auto mt-4 px-6">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        </div>
      )}

      <main className="max-w-4xl mx-auto px-6 py-10">
        {/* ЭКРАН 1: Ввод */}
        {screen === 'input' && (
          <div className="bg-white rounded-2xl shadow-sm border p-8 max-w-2xl mx-auto animate-fade-in-up">
            <h1 className="text-3xl font-bold mb-2">Создайте программу обучения</h1>
            <p className="text-gray-500 mb-8">Опишите тему и объём — ИИ сгенерирует каркас курса за 20 секунд</p>

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Тема программы
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="Например: Python для начинающих"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Объём (часы)
                </label>
                <input
                  type="number"
                  value={hours}
                  onChange={(e) => setHours(Number(e.target.value))}
                  min={16}
                  max={500}
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 mt-1">Рекомендуем от 16 до 500 часов</p>
              </div>

              <button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Генерирую каркас... (до 20 сек)
                  </>
                ) : (
                  <>
                    Сгенерировать <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ЭКРАН 2: Каркас */}
        {screen === 'framework' && framework && (
          <div className="space-y-6 animate-fade-in-up">
            {/* Цель */}
            <div className="bg-white rounded-2xl shadow-sm border p-6">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 uppercase tracking-wide mb-2">
                <GraduationCap className="w-4 h-4" /> Цель программы
              </div>
              <p className="text-lg text-gray-800">{framework.goal}</p>
              <div className="mt-3 text-sm text-gray-500">
                Всего часов: <span className="font-semibold text-gray-900">{framework.total_hours}</span>
              </div>
            </div>

            {/* Модули */}
            <div className="bg-white rounded-2xl shadow-sm border p-6">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 uppercase tracking-wide mb-4">
                <BookOpen className="w-4 h-4" /> Модули программы
              </div>
              <div className="space-y-2">
                {framework.modules.map((mod, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold">
                        {i + 1}
                      </div>
                      <span className="font-medium">{mod.title}</span>
                    </div>
                    <span className="text-sm text-gray-600 font-semibold">{mod.hours} ч</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Компетенции */}
            <div className="bg-white rounded-2xl shadow-sm border p-6">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 uppercase tracking-wide mb-4">
                <CheckCircle2 className="w-4 h-4" /> Карта компетенций
              </div>
              <div className="space-y-3">
                {framework.competencies.map((comp, i) => (
                  <div key={i} className="p-4 border rounded-lg">
                    <div className="font-semibold mb-2">{comp.name}</div>
                    <div className="flex flex-wrap gap-2">
                      {comp.knowledge.map((k, j) => (
                        <span key={j} className="bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full text-xs">
                          {k}
                        </span>
                      ))}
                      {comp.skills.map((s, j) => (
                        <span key={`s${j}`} className="bg-green-100 text-green-800 px-2.5 py-1 rounded-full text-xs">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Кнопка утверждения */}
            <button
              onClick={handleApprove}
              disabled={loading}
              className="w-full bg-green-600 text-white py-4 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors text-lg"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Генерирую тесты и семинары...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5" /> Утвердить каркас и продолжить
                </>
              )}
            </button>
          </div>
        )}

        {/* ЭКРАН 3: Результат */}
        {screen === 'result' && content && (
          <div className="space-y-6 animate-fade-in-up">
            <div className="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-2xl p-6">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center">
                  <CheckCircle2 className="w-7 h-7 text-white" />
                </div>
                <div>
                  <div className="text-xl font-bold">Программа готова! 🎉</div>
                  <div className="text-sm text-gray-600">Скачайте .docx или просмотрите материалы ниже</div>
                </div>
              </div>
            </div>

            {/* Тесты */}
            <div className="bg-white rounded-2xl shadow-sm border p-6">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 uppercase tracking-wide mb-3">
                <FileText className="w-4 h-4" /> Тесты
              </div>
              <div className="whitespace-pre-wrap text-sm text-gray-800 bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                {content.tests}
              </div>
            </div>

            {/* Семинары */}
            <div className="bg-white rounded-2xl shadow-sm border p-6">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 uppercase tracking-wide mb-3">
                <FileText className="w-4 h-4" /> Семинары
              </div>
              <div className="whitespace-pre-wrap text-sm text-gray-800 bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                {content.seminars}
              </div>
            </div>

            {/* Кнопка экспорта */}
            <button
              onClick={handleExport}
              className="w-full bg-blue-600 text-white py-4 rounded-lg font-medium hover:bg-blue-700 flex items-center justify-center gap-2 transition-colors text-lg"
            >
              <Download className="w-5 h-5" /> Скачать .docx
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

// Маленький компонент шага
function Step({ num, label, active, done }: { num: number; label: string; active: boolean; done: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`
        w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all
        ${done ? 'bg-green-500 text-white' : active ? 'bg-blue-600 text-white ring-4 ring-blue-100 animate-pulse' : 'bg-gray-200 text-gray-500'}
      `}>
        {done ? <CheckCircle2 className="w-4 h-4" /> : num}
      </div>
      <span className={`font-medium ${active ? 'text-blue-600' : done ? 'text-green-600' : 'text-gray-400'}`}>
        {label}
      </span>
    </div>
  );
}

export default App;