import { useState, useEffect, Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
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

// --- Error Boundary ---
class ErrorBoundary extends Component<{children: ReactNode}, {hasError: boolean, error: Error | null}> {
  constructor(props: {children: ReactNode}) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("UI Crash:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-6">
          <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-lg max-w-md w-full text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">Что-то пошло не так</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              Произошла ошибка при отображении данных. Возможно, сервер прислал неверный формат.
            </p>
            <button onClick={() => window.location.reload()} className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700">
              Перезагрузить страницу
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

type Screen = 'input' | 'framework' | 'result';

function MainApp() {
  const [screen, setScreen] = useState<Screen>('input');
  const [topic, setTopic] = useState('');
  const [hours, setHours] = useState<number>(72);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [sessionId, setSessionId] = useState<string>('');
  const [framework, setFramework] = useState<Framework | null>(null);
  const [content, setContent] = useState<ContentResponse | null>(null);
  
  const [reviseText, setReviseText] = useState('');
  const [revising, setRevising] = useState(false);

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
    if (!topic.trim() || topic.trim().length < 3) { setError('Тема слишком короткая'); return; }
    if (hours < 16 || hours > 500) { setError('Объём программы должен быть от 16 до 500 часов'); return; }

    setError(null);
    setLoading(true);
    try {
      const res = await generateFramework(topic.trim(), hours);
      setSessionId(res.session_id);
      setFramework(res.framework);
      
      if (res.validation_report) {
        setContent({ validation_report: res.validation_report } as any);
      }
      
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
      console.log("Ответ от /approve:", res);
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-900 dark:to-gray-800 text-gray-900 dark:text-gray-100 transition-colors">
      
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

          <div className="flex items-center mt-4 text-xs">
            <Step num={1} label="Ввод" active={screen === 'input'} done={screen !== 'input'} />
            <div className={`flex-1 h-0.5 mx-2 ${screen !== 'input' ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
            <Step num={2} label="Каркас" active={screen === 'framework'} done={screen === 'result'} />
            <div className={`flex-1 h-0.5 mx-2 ${screen === 'result' ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
            <Step num={3} label="Результат" active={screen === 'result'} done={false} />
          </div>
        </div>
      </header>

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
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Объём (часы)</label>
                <div className="flex items-center w-full border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 transition-colors overflow-hidden focus-within:ring-2 focus-within:ring-blue-500">
                  <button
                    type="button"
                    onClick={() => setHours(prev => Math.max(16, prev - 1))}
                    disabled={loading || hours <= 16}
                    className="px-4 py-3 text-gray-500 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50"
                  >
                    <Minus className="w-5 h-5" />
                  </button>
                  <input
                    type="number"
                    value={hours === 0 ? '' : hours}
                    onChange={(e) => setHours(e.target.value === '' ? 0 : parseInt(e.target.value, 10))}
                    onBlur={() => { if (hours < 16) setHours(16); if (hours > 500) setHours(500); }}
                    min={16} max={500}
                    disabled={loading}
                    className="flex-1 w-full bg-transparent text-center font-semibold text-lg focus:outline-none dark:text-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <button
                    type="button"
                    onClick={() => setHours(prev => Math.min(500, prev + 1))}
                    disabled={loading || hours >= 500}
                    className="px-4 py-3 text-gray-500 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
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

        {screen === 'framework' && framework && (
          <div className="space-y-6 animate-fade-in-up">
            {content?.validation_report?.hours_match !== undefined && (
              <div className={`p-4 rounded-lg border ${
                content.validation_report.hours_match 
                  ? 'bg-green-100 border-green-500 text-green-800 dark:bg-green-900/30 dark:border-green-700 dark:text-green-300' 
                  : 'bg-red-100 border-red-500 text-red-800 dark:bg-red-900/30 dark:border-red-700 dark:text-red-300'
              }`}>
                <h3 className="font-bold mb-2">
                  {content.validation_report.hours_match ? '✅ Отчёт автопроверки' : '⚠️ Внимание: есть расхождения'}
                </h3>
                <p>Сумма часов: <strong>{content.validation_report.calculated_total}</strong> / {content.validation_report.expected_total}</p>
                <p>Покрытие компетенций: {content.validation_report.competency_coverage ? 'Достаточно' : 'Мало'}</p>
              </div>
            )}

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase mb-2">
                <GraduationCap className="w-4 h-4" /> Цель программы
              </div>
              <p className="text-lg text-gray-800 dark:text-gray-200">{framework.goal || 'Цель не указана'}</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase mb-4">
                <BookOpen className="w-4 h-4" /> Модули программы
              </div>
              <div className="space-y-2">
                {framework.modules?.map((mod: any, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold">{i + 1}</div>
                      <span className="font-medium">{mod.title || mod.name || 'Без названия'}</span>
                    </div>
                    {mod.hours && <span className="font-semibold">{mod.hours} ч</span>}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase mb-4">
                <CheckCircle2 className="w-4 h-4" /> Карта компетенций
              </div>
              <div className="space-y-3">
                {framework.competencies?.map((comp, i) => (
                  <div key={i} className="p-4 border dark:border-gray-700 rounded-lg">
                    <div className="font-semibold mb-2">{comp.name || 'Компетенция'}</div>
                    <div className="flex flex-wrap gap-2">
                      {comp.knowledge?.map((k, j) => <span key={j} className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs">{k}</span>)}
                      {comp.skills?.map((s, j) => <span key={`s${j}`} className="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs">{s}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 border-l-4 border-l-purple-500 transition-colors">
              <div className="flex items-center gap-2 text-xs font-semibold text-purple-600 uppercase mb-3">
                <Sparkles className="w-4 h-4" /> Точечная доработка
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={reviseText}
                  onChange={(e) => setReviseText(e.target.value)}
                  placeholder="Например: добавь модуль по асинхронности"
                  className="flex-1 px-4 py-2 border rounded-lg bg-gray-50 dark:bg-gray-700 text-sm"
                  disabled={revising}
                />
                <button onClick={handleRevise} disabled={revising || !reviseText.trim()} className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2">
                  {revising ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  Применить
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

        {screen === 'result' && content && (
          <div className="space-y-6 animate-fade-in-up">
            <div className="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border border-green-200 dark:border-green-800 rounded-2xl p-6 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center">
                  <CheckCircle2 className="w-7 h-7 text-white" />
                </div>
                <div>
                  <div className="text-xl font-bold">Программа готова! 🎉</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Скачайте файлы или просмотрите материалы ниже</div>
                </div>
              </div>
            </div>

            {content.content?.tests?.questions && content.content.tests.questions.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
                <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 uppercase mb-4">
                  <FileText className="w-4 h-4" /> Тесты
                </div>
                <div className="space-y-4">
                  {content.content.tests.questions.map((q, idx) => (
                    <div key={idx} className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg border dark:border-gray-700">
                      <p className="font-medium text-gray-900 dark:text-gray-100">{idx + 1}. {q.question}</p>
                      <ul className="mt-2 space-y-1 text-sm text-gray-700 dark:text-gray-300">
                        {q.options?.map((opt, i) => (
                          <li key={i} className={opt === q.correct_answer ? "text-green-600 font-bold" : ""}>
                            {opt === q.correct_answer ? "✓ " : "○ "} {opt}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {content.content?.seminars?.task && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
                <div className="flex items-center gap-2 text-xs font-semibold text-orange-600 uppercase mb-4">
                  <FileText className="w-4 h-4" /> Задание для семинара
                </div>
                <p className="text-gray-800 dark:text-gray-200 mb-3">{content.content.seminars.task}</p>
                {content.content.seminars.criteria && (
                  <div className="bg-orange-50 dark:bg-orange-900/20 p-4 rounded-lg text-sm text-orange-900 dark:text-orange-200 border border-orange-200 dark:border-orange-800">
                    <strong>Критерии оценки:</strong>
                    <p className="whitespace-pre-wrap mt-1">{content.content.seminars.criteria}</p>
                  </div>
                )}
              </div>
            )}

            {content.content?.lectures?.modules_plan && content.content.lectures.modules_plan.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
                <div className="flex items-center gap-2 text-xs font-semibold text-purple-600 uppercase mb-4">
                  <BookOpen className="w-4 h-4" /> Планы лекций
                </div>
                <div className="space-y-4">
                  {content.content.lectures.modules_plan.map((mod, idx) => (
                    <div key={idx} className="border-l-4 border-purple-400 pl-4">
                      <h4 className="font-bold text-gray-800 dark:text-gray-200">{mod.module_title}</h4>
                      <ul className="list-disc list-inside mt-2 text-sm text-gray-700 dark:text-gray-300">
                        {mod.theses?.map((thesis, i) => <li key={i}>{thesis}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border dark:border-gray-700 p-6 transition-colors">
              <h3 className="text-lg font-bold mb-4">Скачать файлы:</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button onClick={() => handleDownload('docx')} className="flex items-center justify-center gap-2 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700">
                  <FileDown className="w-5 h-5" /> Word
                </button>
                <button onClick={() => handleDownload('pptx')} className="flex items-center justify-center gap-2 bg-purple-600 text-white py-3 rounded-lg font-medium hover:bg-purple-700">
                  <Presentation className="w-5 h-5" /> Презентация
                </button>
                <button onClick={() => handleDownload('lms')} className="flex items-center justify-center gap-2 bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700">
                  <Download className="w-5 h-5" /> LMS (.txt)
                </button>
              </div>
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

export default function App() {
  return (
    <ErrorBoundary>
      <MainApp />
    </ErrorBoundary>
  );
}