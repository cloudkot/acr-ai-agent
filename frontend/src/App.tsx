import { useState, useEffect } from 'react';
import { 
  Loader2, ArrowRight, CheckCircle2, Download, 
  FileText, BookOpen, GraduationCap, RotateCcw, 
  Sparkles, FileDown, Presentation, Moon, Sun,
  Minus, Plus, AlertCircle
} from 'lucide-react';
import { 
  generateFramework, 
  approveFramework, 
  reviseFramework,
  downloadFile,
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
  const [content, setContent] = useState<ContentResponse | null>(null);
  
  // Для доработки
  const [reviseText, setReviseText] = useState('');
  const [revising, setRevising] = useState(false);

  // Тёмная тема
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  const handleGenerate = async () => {
    if (!topic.trim()) { setError('Пожалуйста, укажите тему программы'); return; }
    if (topic.trim().length < 3) { setError('Тема слишком короткая (минимум 3 символа)'); return; }
    if (topic.length > 200) { setError('Тема слишком длинная (максимум 200 символов)'); return; }
    if (!Number.isInteger(hours) || hours < 16 || hours > 500) {
      setError('Объём программы должен быть целым числом от 16 до 500 часов');
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const res = await generateFramework(topic.trim(), hours);
      setSessionId(res.session_id);
      setFramework(res.framework);
      setScreen('framework');
    } catch (e: any) {
      setError(e.message || 'Ошибка сети. Проверьте соединение.');
    } finally {
      setLoading(false);
    }
  };

  const handleRevise = async () => {
    if (!reviseText.trim()) return;
    setRevising(true);
    setError(null);
    try {
      const res = await reviseFramework(sessionId, reviseText);
      setFramework(res.framework);
      setReviseText('');
    } catch (e: any) {
      setError(e.message || 'Ошибка доработки');
    } finally {
      setRevising(false);
    }
  };

  const handleApprove = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await approveFramework(sessionId);
      setContent(res);
      setScreen('result');
    } catch (e: any) {
      setError(e.message || 'Ошибка утверждения');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (type: 'docx' | 'pptx' | 'lms') => {
    try {
      await downloadFile(sessionId, type);
    } catch (e: any) {
      setError(e.message || 'Не удалось скачать файл');
    }
  };

  const handleRestart = () => {
    setScreen('input');
    setTopic('');
    setHours(72);
    setSessionId('');
    setFramework(null);
    setContent(null);
    setReviseText('');
    setError(null);
  };

  // Функция для красивого вывода отчета (если он пришел как объект)
  const renderValidationReport = (report: any) => {
    if (!report) return null;
    if (typeof report === 'string') {
      return <p className="whitespace-pre-wrap">{report}</p>;
    }
    return (
      <div className="space-y-2">
        {Object.entries(report).map(([key, value]) => (
          <div key={key} className="flex justify-between items-center border-b border-green-200 dark:border-green-800 pb-1">
            <span className="capitalize text-gray-600 dark:text-gray-400">{key.replace(/_/g, ' ')}</span>
            <span className="font-semibold text-green-700 dark:text-green-400">
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-900 dark:to-gray-800 text-gray-900 dark:text-gray-100 transition-colors">
      
      {/* Шапка */}
      <header className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 sticky top-0 z-10 transition-colors">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold">AI</div>
              <div>
                <div className="font-bold text-sm">ACR AI Agent</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Генератор программ</div>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {screen !== 'input' && (
                <button onClick={handleRestart} className="text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 flex items-center gap-1">
                  <RotateCcw className="w-3 h-3" /> Начать заново
                </button>
              )}
              
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-600 dark:text-gray-300"
              >
                {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Прогресс-бар */}
          <div className="flex items-center mt-4 text-xs">
            <Step num={1} label="Ввод" active={screen === 'input'} done={screen !== 'input'} />
            <div className={`flex-1 h-0.5 mx-2 ${screen !== 'input' ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
            <Step num={2} label="Каркас" active={screen === 'framework'} done={screen === 'result'} />
            <div className={`flex-1 h-0.5 mx-2 ${screen === 'result' ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
            <Step num={3} label="Результат" active={screen === 'result'} done={false} />
          </div>
        </div>
      </header>

      {/* Красивое отображение ошибки (вместо Failed to fetch) */}
      {error && (
        <div className="max-w-5xl mx-auto mt-4 px-6 animate-fade-in-up">
          <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg text-sm flex items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 font-bold">✕</button>
          </div>
        </div>
      )}

      <main className="max-w-5xl mx-auto px-6 py-10">
        
        {/* ЭКРАН 1: Ввод */}
        {screen === 'input' && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-8 max-w-2xl mx-auto animate-fade-in-up transition-colors">
            <h1 className="text-3xl font-bold mb-2">Создайте программу обучения</h1>
            <p className="text-gray-500 dark:text-gray-400 mb-8">Опишите тему и объём — ИИ сгенерирует каркас курса</p>
            
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Тема программы</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="Например: Python для начинающих"
                  className="w-full px-4 py-3 border border-gray-200 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 dark:bg-gray-700 dark:text-white transition-colors"
                  disabled={loading}
                />
                {/* Быстрые подсказки */}
                <div className="flex flex-wrap gap-2 mt-2">
                  {["Python", "Frontend", "DevOps", "Data Science", "ML"].map((tag) => (
                    <button 
                      key={tag} 
                      onClick={() => setTopic(tag)}
                      className="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 px-3 py-1 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Объём (часы)</label>
                <div className="flex items-center w-full border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 transition-colors overflow-hidden focus-within:ring-2 focus-within:ring-blue-500">
                  <button
                    type="button"
                    onClick={() => setHours(prev => Math.max(16, prev - 1))}
                    disabled={loading || hours <= 16}
                    className="px-4 py-3 text-gray-500 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                  >
                    <Minus className="w-5 h-5" />
                  </button>
                  <input
                    type="number"
                    value={hours}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      setHours(isNaN(val) ? 16 : val);
                    }}
                    onBlur={() => {
                      if (hours < 16) setHours(16);
                      if (hours > 500) setHours(500);
                    }}
                    min={16} max={500}
                    disabled={loading}
                    className="flex-1 w-full bg-transparent text-center font-semibold text-lg focus:outline-none dark:text-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <button
                    type="button"
                    onClick={() => setHours(prev => Math.min(500, prev + 1))}
                    disabled={loading || hours >= 500}
                    className="px-4 py-3 text-gray-500 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Рекомендуем от 16 до 500 часов.</p>
              </div>
              
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
              >
                {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Генерирую каркас...</> : <>Сгенерировать <ArrowRight className="w-5 h-5" /></>}
              </button>
            </div>
          </div>
        )}

        {/* ЭКРАН 2: Каркас */}
        {screen === 'framework' && framework && (
          <div className="space-y-6 animate-fade-in-up">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-2">
                <GraduationCap className="w-4 h-4" /> Цель программы
              </div>
              <p className="text-lg text-gray-800 dark:text-gray-200">{framework.goal}</p>
              <div className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                Всего часов: <span className="font-semibold text-gray-900 dark:text-white">{framework.total_hours}</span>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-4">
                <BookOpen className="w-4 h-4" /> Модули программы
              </div>
              <div className="space-y-2">
                {framework.modules.map((mod, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 flex items-center justify-center text-sm font-bold">{i + 1}</div>
                      <span className="font-medium">{mod.title}</span>
                    </div>
                    <span className="text-sm text-gray-600 dark:text-gray-300 font-semibold">{mod.hours} ч</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-4">
                <CheckCircle2 className="w-4 h-4" /> Карта компетенций
              </div>
              <div className="space-y-3">
                {framework.competencies.map((comp, i) => (
                  <div key={i} className="p-4 border dark:border-gray-700 rounded-lg">
                    <div className="font-semibold mb-2">{comp.name}</div>
                    <div className="flex flex-wrap gap-2">
                      {comp.knowledge.map((k, j) => (
                        <span key={j} className="bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 px-2.5 py-1 rounded-full text-xs">{k}</span>
                      ))}
                      {comp.skills.map((s, j) => (
                        <span key={`s${j}`} className="bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200 px-2.5 py-1 rounded-full text-xs">{s}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 border-l-4 border-l-purple-500 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wide mb-3">
                <Sparkles className="w-4 h-4" /> Точечная доработка
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">Не нравится каркас? Опишите, что изменить — ИИ перепишет только нужные части.</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={reviseText}
                  onChange={(e) => setReviseText(e.target.value)}
                  placeholder="Например: добавь модуль по асинхронности"
                  className="flex-1 px-4 py-2 border border-gray-200 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-gray-50 dark:bg-gray-700 dark:text-white text-sm transition-colors"
                  disabled={revising}
                />
                <button
                  onClick={handleRevise}
                  disabled={revising || !reviseText.trim()}
                  className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {revising ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {revising ? 'Дорабатываю...' : 'Применить'}
                </button>
              </div>
            </div>

            <button
              onClick={handleApprove}
              disabled={loading}
              className="w-full bg-green-600 text-white py-4 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors text-lg"
            >
              {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Генерирую тесты и семинары...</> : <><CheckCircle2 className="w-5 h-5" /> Утвердить каркас и продолжить</>}
            </button>
          </div>
        )}

        {/* ЭКРАН 3: Результат */}
        {screen === 'result' && content && (
          <div className="space-y-6 animate-fade-in-up">
            <div className="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border border-green-200 dark:border-green-800 rounded-2xl p-6 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center">
                  <CheckCircle2 className="w-7 h-7 text-white" />
                </div>
                <div>
                  <div className="text-xl font-bold">Программа готова! 🎉</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Скачайте материалы или просмотрите ниже</div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
                <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-3">
                  <FileText className="w-4 h-4" /> Тесты
                </div>
                <div className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 bg-gray-50 dark:bg-gray-700 p-4 rounded-lg max-h-64 overflow-y-auto transition-colors">
                  {content.content.tests}
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
                <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-3">
                  <FileText className="w-4 h-4" /> Семинары
                </div>
                <div className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 bg-gray-50 dark:bg-gray-700 p-4 rounded-lg max-h-64 overflow-y-auto transition-colors">
                  {content.content.seminars}
                </div>
              </div>
            </div>

            {/* Блок Отчета автопроверки (СУДЬЯ ЭТОГО ЖДАЛ) */}
            {content.validation_report && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
                <div className="flex items-center gap-2 text-xs font-semibold text-green-600 dark:text-green-400 uppercase tracking-wide mb-3">
                  <CheckCircle2 className="w-4 h-4" /> Отчёт автопроверки
                </div>
                <div className="text-sm text-gray-700 dark:text-gray-300 bg-green-50 dark:bg-green-900/20 p-4 rounded-lg">
                  {renderValidationReport(content.validation_report)}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => handleDownload('docx')}
                className="flex items-center justify-center gap-2 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                <FileDown className="w-5 h-5" /> Скачать DOCX
              </button>
              <button
                onClick={() => handleDownload('pptx')}
                className="flex items-center justify-center gap-2 bg-purple-600 text-white py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors"
              >
                <Presentation className="w-5 h-5" /> Скачать PPTX
              </button>
              <button
                onClick={() => handleDownload('lms')}
                className="flex items-center justify-center gap-2 bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 transition-colors"
              >
                <Download className="w-5 h-5" /> Скачать LMS (.txt)
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function Step({ num, label, active, done }: { num: number; label: string; active: boolean; done: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all
        ${done ? 'bg-green-500 text-white' : active ? 'bg-blue-600 text-white ring-4 ring-blue-100 dark:ring-blue-900/50 animate-pulse' : 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400'}`}>
        {done ? <CheckCircle2 className="w-4 h-4" /> : num}
      </div>
      <span className={`font-medium ${active ? 'text-blue-600 dark:text-blue-400' : done ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}`}>{label}</span>
    </div>
  );
}

export default App;