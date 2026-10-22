import { useState, useEffect, Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { 
  Loader2, ArrowRight, CheckCircle2, Download, 
  FileText, BookOpen, GraduationCap, RotateCcw, 
  Sparkles, FileDown, Presentation, Moon, Sun,
  Minus, Plus, AlertCircle, Paperclip, X, Library,
  TrendingUp, Coins, Cpu
} from 'lucide-react';
import { 
  generateFramework, 
  approveFramework, 
  reviseFramework,
  uploadReference,
  downloadFile,
  getAnalytics,
  type Framework,
  type ContentResponse,
  type Analytics
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
  const [hoursInput, setHoursInput] = useState<string>('72');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [sessionId, setSessionId] = useState<string>('');
  const [framework, setFramework] = useState<Framework | null>(null);
  const [content, setContent] = useState<ContentResponse | null>(null);
  
  const [reviseText, setReviseText] = useState('');
  const [revising, setRevising] = useState(false);

  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referenceText, setReferenceText] = useState<string>('');
  const [uploadingFile, setUploadingFile] = useState(false);

  // Аналитика
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Сохранение состояния
  const [isRestored, setIsRestored] = useState(false);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  // Восстановление состояния при перезагрузке
  useEffect(() => {
    try {
      const saved = localStorage.getItem('appState');
      if (saved) {
        const data = JSON.parse(saved);
        if (data.screen) setScreen(data.screen);
        if (data.topic) setTopic(data.topic);
        if (data.hours) setHours(data.hours);
        if (data.hoursInput) setHoursInput(data.hoursInput);
        if (data.sessionId) setSessionId(data.sessionId);
        if (data.framework) setFramework(data.framework);
        if (data.content) setContent(data.content);
      }
    } catch (e) {
      console.warn('Не удалось восстановить состояние');
    } finally {
      setIsRestored(true);
    }
  }, []);

  // Сохранение состояния при каждом изменении
  useEffect(() => {
    if (!isRestored) return;
    const state = { screen, topic, hours, hoursInput, sessionId, framework, content };
    localStorage.setItem('appState', JSON.stringify(state));
  }, [screen, topic, hours, hoursInput, sessionId, framework, content, isRestored]);

  // Загрузка аналитики
  useEffect(() => {
    getAnalytics()
      .then(setAnalytics)
      .catch(() => setAnalytics(null));
  }, []);

  const handleHoursChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setHoursInput(val);
    if (val !== '') {
      setHours(parseInt(val, 10) || 0);
    } else {
      setHours(0);
    }
  };

  const handleHoursBlur = () => {
    let val = parseInt(hoursInput, 10);
    if (isNaN(val) || val < 16) val = 16;
    if (val > 500) val = 500;
    setHours(val);
    setHoursInput(val.toString());
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setReferenceFile(file);
    setUploadingFile(true);
    setError(null);
    try {
      const res = await uploadReference(file);
      setReferenceText(res.full_text);
    } catch (err: any) {
      setError(err.message || 'Не удалось загрузить файл. Возможно, бэкенд не поддерживает загрузку.');
      setReferenceFile(null);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleRemoveReference = () => {
    setReferenceFile(null);
    setReferenceText('');
  };

  const handleGenerate = async () => {
    if (!topic.trim() || topic.trim().length < 2) { setError('Тема слишком короткая (минимум 2 символа)'); return; }
    
    let finalHours = parseInt(hoursInput, 10);
    if (isNaN(finalHours) || finalHours < 16 || finalHours > 500) {
      setError('Объём программы должен быть от 16 до 500 часов');
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const res = await generateFramework(topic.trim(), finalHours, 'auto', referenceText || undefined);
      setSessionId(res.session_id);
      setFramework(res.framework);
      
      if (res.validation_report) {
        setContent({ validation_report: res.validation_report } as ContentResponse);
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
      setContent(res);
      setScreen('result');
      
      // Обновляем аналитику
      try {
        const updatedAnalytics = await getAnalytics();
        setAnalytics(updatedAnalytics);
      } catch (e) {
        console.warn('Не удалось обновить аналитику:', e);
      }
    } catch (e: any) {
      setError(e.message || 'Ошибка утверждения');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (type: 'docx' | 'pptx' | 'lms' | 'moodle' | 'json') => {
    downloadFile(sessionId, type);
  };

  const handleRestart = () => {
    setScreen('input');
    setTopic('');
    setHours(72);
    setHoursInput('72');
    setSessionId('');
    setFramework(null);
    setContent(null);
    setReviseText('');
    setReferenceFile(null);
    setReferenceText('');
    setError(null);
    localStorage.removeItem('appState');
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#0F172A] text-gray-900 dark:text-gray-100 transition-colors duration-300 relative overflow-hidden">
      
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-400/20 rounded-full blur-3xl -z-10 pointer-events-none"></div>
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl -z-10 pointer-events-none"></div>

      <header className="bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 sticky top-0 z-50 transition-colors">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/30">
                AI
              </div>
              <div>
                <div className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
                  ACR Agent
                </div>
                <div className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">EdTech Generator</div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              {screen !== 'input' && (
                <button onClick={handleRestart} className="text-xs font-medium text-gray-500 hover:text-blue-600 flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all">
                  <RotateCcw className="w-3.5 h-3.5" /> Новый проект
                </button>
              )}
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
              >
                {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div className="flex items-center mt-6 text-xs font-medium">
            <Step num={1} label="Параметры" active={screen === 'input'} done={screen !== 'input'} />
            <div className={`flex-1 h-1 mx-3 rounded-full transition-all duration-500 ${screen !== 'input' ? 'bg-gradient-to-r from-green-400 to-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
            <Step num={2} label="Каркас" active={screen === 'framework'} done={screen === 'result'} />
            <div className={`flex-1 h-1 mx-3 rounded-full transition-all duration-500 ${screen === 'result' ? 'bg-gradient-to-r from-green-400 to-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
            <Step num={3} label="Материалы" active={screen === 'result'} done={false} />
          </div>
        </div>
      </header>

      {error && (
        <div className="max-w-5xl mx-auto mt-6 px-6 animate-fade-in-up">
          <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 text-red-700 dark:text-red-300 px-4 py-3 rounded-r-lg text-sm flex items-start justify-between gap-3 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span className="font-medium">{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 font-bold">✕</button>
          </div>
        </div>
      )}

      <main className="max-w-4xl mx-auto px-6 py-12 relative z-10">
        
        {screen === 'input' && (
          <div className="animate-fade-in-up">
            <div className="text-center mb-10">
              <h1 className="text-4xl md:text-5xl font-extrabold mb-4 tracking-tight">
                Создайте программу за <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">минуты</span>
              </h1>
              <p className="text-lg text-gray-500 dark:text-gray-400 max-w-2xl mx-auto">
                Укажите тему и объём — ИИ-агент сформирует каркас, компетенции и учебный план.
              </p>
            </div>

            <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl rounded-3xl shadow-2xl shadow-blue-500/5 border border-white dark:border-gray-700 p-8 max-w-2xl mx-auto">
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Тема программы</label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Например: Python для начинающих"
                    className="w-full px-5 py-4 text-lg border-2 border-gray-100 dark:border-gray-700 rounded-xl focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none bg-gray-50 dark:bg-gray-900 dark:text-white transition-all"
                    disabled={loading}
                  />
                  <div className="flex flex-wrap gap-2 mt-3">
                    {["Python", "Frontend", "DevOps", "Data Science", "ML"].map((tag) => (
                      <button 
                        key={tag} 
                        onClick={() => setTopic(tag)}
                        className="text-xs font-semibold bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 px-4 py-1.5 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors border border-blue-100 dark:border-blue-800"
                      >
                        + {tag}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Референсы (опционально)</label>
                  {!referenceFile ? (
                    <label className="flex items-center justify-center gap-2 w-full px-5 py-4 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-xl cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-all">
                      {uploadingFile ? <Loader2 className="w-5 h-5 animate-spin text-blue-500" /> : <Paperclip className="w-5 h-5 text-gray-400" />}
                      <span className="text-sm font-medium text-gray-500">{uploadingFile ? 'Загрузка...' : 'Прикрепить .docx или .pdf'}</span>
                      <input type="file" accept=".docx,.pdf,.txt" className="hidden" onChange={handleFileUpload} disabled={uploadingFile || loading} />
                    </label>
                  ) : (
                    <div className="flex items-center justify-between w-full px-5 py-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                      <div className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-300">
                        <CheckCircle2 className="w-5 h-5" /> {referenceFile.name}
                      </div>
                      <button onClick={handleRemoveReference} className="p-1 text-green-600 hover:text-red-500 transition-colors">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Объём программы (часы)</label>
                  <div className="flex items-center w-full border-2 border-gray-100 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-900 transition-all focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => {
                        const newVal = Math.max(16, hours - 1);
                        setHours(newVal);
                        setHoursInput(newVal.toString());
                      }}
                      disabled={loading || hours <= 16}
                      className="px-5 py-4 text-gray-400 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
                    >
                      <Minus className="w-6 h-6" />
                    </button>
                    <input
                      type="number"
                      value={hoursInput}
                      onChange={handleHoursChange}
                      onBlur={handleHoursBlur}
                      className="flex-1 w-full bg-transparent text-center font-bold text-2xl focus:outline-none dark:text-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                      disabled={loading}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const newVal = Math.min(500, hours + 1);
                        setHours(newVal);
                        setHoursInput(newVal.toString());
                      }}
                      disabled={loading || hours >= 500}
                      className="px-5 py-4 text-gray-400 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
                    >
                      <Plus className="w-6 h-6" />
                    </button>
                  </div>
                  <p className="text-xs text-gray-400 mt-2 font-medium">Допустимый диапазон: от 16 до 500 часов</p>
                </div>
                
                <button
                  onClick={handleGenerate}
                  disabled={loading || uploadingFile}
                  className="w-full relative group bg-gray-900 dark:bg-white text-white dark:text-gray-900 py-4 rounded-xl font-bold text-lg hover:shadow-xl hover:shadow-gray-900/20 dark:hover:shadow-white/20 disabled:opacity-50 flex items-center justify-center gap-3 transition-all duration-300 overflow-hidden"
                >
                  {loading ? (
                    <><Loader2 className="w-6 h-6 animate-spin" /> Анализирую...</>
                  ) : (
                    <>
                      <span className="relative z-10">Сгенерировать каркас</span>
                      <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
                      <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {screen === 'framework' && framework && (
          <div className="space-y-6 animate-fade-in-up">
            {content?.validation_report && (
              <div className={`p-5 rounded-xl border-l-4 shadow-sm ${
                content.validation_report.hours_match 
                  ? 'bg-green-50 border-green-500 text-green-800 dark:bg-green-900/20 dark:text-green-300' 
                  : 'bg-red-50 border-red-500 text-red-800 dark:bg-red-900/20 dark:text-red-300'
              }`}>
                <h3 className="font-bold flex items-center gap-2 text-lg mb-3">
                  {content.validation_report.hours_match ? <CheckCircle2 className="w-5 h-5"/> : <AlertCircle className="w-5 h-5"/>}
                  Отчёт автопроверки
                </h3>
                
                <div className="space-y-2 text-sm">
                  <p>Часы: <strong>{content.validation_report.calculated_total}</strong> / {content.validation_report.expected_total} 
                    <span className="ml-2">({content.validation_report.hours_match ? 'Совпадает' : 'Ошибка'})</span>
                  </p>

                  {content.validation_report.deep_coverage && (
                    <div>
                      <p className={content.validation_report.deep_coverage.coverage_ok ? "text-green-700 dark:text-green-400" : "text-orange-600 dark:text-orange-400"}>
                        Покрытие компетенций: <strong>{content.validation_report.deep_coverage.tested_count}</strong> из {content.validation_report.deep_coverage.total_competencies}
                      </p>
                      {!content.validation_report.deep_coverage.coverage_ok && content.validation_report.deep_coverage.uncovered.length > 0 && (
                        <ul className="mt-1 list-disc pl-5 text-red-500">
                          {content.validation_report.deep_coverage.uncovered.map((comp, i) => (
                            <li key={i}>Не проверено: {comp}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {content.validation_report.sources_check?.warnings && content.validation_report.sources_check.warnings.length > 0 && (
                    <div className="mt-2 text-orange-600 dark:text-orange-400">
                      <strong className="block">Внимание по источникам:</strong>
                      <ul className="list-disc pl-5">
                        {content.validation_report.sources_check.warnings.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
              <div className="flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest mb-3">
                <GraduationCap className="w-4 h-4" /> Цель программы
              </div>
              <p className="text-lg font-medium text-gray-800 dark:text-gray-200 leading-relaxed">{framework.goal || 'Цель не указана'}</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
              <div className="flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest mb-4">
                <BookOpen className="w-4 h-4" /> Модули программы
              </div>
              <div className="space-y-2">
                {framework.modules?.map((mod: any, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl border border-gray-100 dark:border-gray-700">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 flex items-center justify-center font-bold text-sm">{i + 1}</div>
                      <span className="font-semibold text-gray-800 dark:text-gray-200">{mod.title || mod.name || 'Без названия'}</span>
                    </div>
                    {mod.hours && <span className="text-sm font-bold text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded-md">{mod.hours} ч</span>}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
              <div className="flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest mb-4">
                <CheckCircle2 className="w-4 h-4" /> Карта компетенций
              </div>
              <div className="grid gap-4">
                {framework.competencies?.map((comp, i) => (
                  <div key={i} className="p-4 border border-gray-100 dark:border-gray-700 rounded-xl bg-gray-50/50 dark:bg-gray-800/50">
                    <div className="font-bold text-gray-800 dark:text-gray-200 mb-2">{comp.name || 'Компетенция'}</div>
                    <div className="flex flex-wrap gap-2">
                      {comp.knowledge?.map((k, j) => <span key={j} className="bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 px-2.5 py-1 rounded-lg text-xs font-medium">{k}</span>)}
                      {comp.skills?.map((s, j) => <span key={`s${j}`} className="bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 px-2.5 py-1 rounded-lg text-xs font-medium">{s}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-purple-100 dark:border-purple-900/30 p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-2xl -mr-10 -mt-10"></div>
              <div className="flex items-center gap-2 text-xs font-bold text-purple-600 dark:text-purple-400 uppercase tracking-widest mb-3 relative z-10">
                <Sparkles className="w-4 h-4" /> Точечная доработка
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 relative z-10">Не нравится каркас? ИИ перепишет только нужные части.</p>
              <div className="flex gap-2 relative z-10">
                <input
                  type="text"
                  value={reviseText}
                  onChange={(e) => setReviseText(e.target.value)}
                  placeholder="Например: добавь модуль по асинхронности"
                  className="flex-1 px-4 py-3 border border-gray-200 dark:border-gray-700 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none bg-gray-50 dark:bg-gray-900 text-sm"
                  disabled={revising}
                />
                <button onClick={handleRevise} disabled={revising || !reviseText.trim()} className="bg-purple-600 text-white px-5 py-3 rounded-xl text-sm font-bold hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2 transition-colors">
                  {revising ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  Применить
                </button>
              </div>
            </div>

            <button
              onClick={handleApprove}
              disabled={loading}
              className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white py-4 rounded-xl font-bold text-lg hover:shadow-xl hover:shadow-green-500/30 disabled:opacity-50 flex items-center justify-center gap-3 transition-all"
            >
              {loading ? <><Loader2 className="w-6 h-6 animate-spin" /> Генерирую материалы...</> : <><CheckCircle2 className="w-6 h-6" /> Утвердить и продолжить</>}
            </button>
          </div>
        )}

        {screen === 'result' && content && (
          <div className="space-y-6 animate-fade-in-up">
            <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-3xl p-8 text-white shadow-2xl shadow-green-500/20 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -mr-20 -mt-20"></div>
              <div className="relative z-10 flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center shadow-inner">
                  <CheckCircle2 className="w-10 h-10 text-white" />
                </div>
                <div>
                  <h2 className="text-3xl font-extrabold mb-1">Программа готова! 🎉</h2>
                  <p className="text-green-100 font-medium">Все материалы сгенерированы и готовы к экспорту.</p>
                </div>
              </div>
            </div>

            {/* Кнопка "Новый проект" на экране результата */}
            <button
              onClick={handleRestart}
              className="flex items-center justify-center gap-2 w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 py-3 rounded-xl font-bold hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
            >
              <RotateCcw className="w-5 h-5" /> Создать новую программу
            </button>

            {/* ВИДЖЕТ АНАЛИТИКИ */}
            {analytics && (
              <div className="flex gap-2 sm:gap-4 p-4 bg-white dark:bg-gray-800 rounded-2xl border border-blue-100 dark:border-blue-900/50 shadow-lg">
                <div className="flex-1 text-center border-r border-gray-100 dark:border-gray-700">
                  <div className="text-xl sm:text-2xl font-extrabold text-blue-600 dark:text-blue-400">{analytics.completed_programs}</div>
                  <div className="text-[10px] sm:text-xs text-gray-500 uppercase tracking-wide mt-1 flex items-center justify-center gap-1"><TrendingUp className="w-3 h-3"/> Программ</div>
                </div>
                <div className="flex-1 text-center border-r border-gray-100 dark:border-gray-700">
                  <div className="text-xl sm:text-2xl font-extrabold text-purple-600 dark:text-purple-400">{analytics.total_tokens_used.toLocaleString()}</div>
                  <div className="text-[10px] sm:text-xs text-gray-500 uppercase tracking-wide mt-1 flex items-center justify-center gap-1"><Cpu className="w-3 h-3"/> Токенов</div>
                </div>
                <div className="flex-1 text-center">
                  <div className="text-xl sm:text-2xl font-extrabold text-green-600 dark:text-green-400">{analytics.total_cost_rub} ₽</div>
                  <div className="text-[10px] sm:text-xs text-gray-500 uppercase tracking-wide mt-1 flex items-center justify-center gap-1"><Coins className="w-3 h-3"/> Потрачено</div>
                </div>
              </div>
            )}

            {content.content?.tests?.questions && content.content.tests.questions.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2 text-sm font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest">
                    <FileText className="w-5 h-5" /> Тесты
                  </div>
                  <span className="bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 px-3 py-1 rounded-full text-xs font-bold">
                    {content.content.tests.questions.length} вопросов
                  </span>
                </div>
                <div className="space-y-4">
                  {content.content.tests.questions.map((q, idx) => (
                    <div key={idx} className="bg-gray-50 dark:bg-gray-900/50 p-5 rounded-xl border border-gray-100 dark:border-gray-700">
                      <p className="font-bold text-gray-900 dark:text-gray-100 mb-3 text-lg">{idx + 1}. {q.question}</p>
                      <ul className="space-y-2 text-sm">
                        {q.options?.map((opt, i) => (
                          <li key={i} className={`flex items-center gap-2 p-2 rounded-lg ${opt === q.correct_answer ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 font-bold border border-green-200 dark:border-green-800" : "text-gray-600 dark:text-gray-400"}`}>
                            <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${opt === q.correct_answer ? "border-green-500 bg-green-500" : "border-gray-300 dark:border-gray-600"}`}>
                              {opt === q.correct_answer && <CheckCircle2 className="w-3 h-3 text-white" />}
                            </div>
                            {opt}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {content.content?.seminars && content.content.seminars.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2 text-sm font-bold text-orange-600 dark:text-orange-400 uppercase tracking-widest">
                    <FileText className="w-5 h-5" /> Семинары
                  </div>
                  <span className="bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-300 px-3 py-1 rounded-full text-xs font-bold">
                    {content.content.seminars.length} заданий
                  </span>
                </div>
                <div className="space-y-4">
                  {content.content.seminars.map((seminar, idx) => (
                    <div key={idx} className="bg-orange-50/50 dark:bg-orange-900/10 p-5 rounded-xl border border-orange-100 dark:border-orange-900/30">
                      <p className="font-bold text-orange-900 dark:text-orange-200 mb-2">Семинар {idx + 1}: {seminar.task}</p>
                      {seminar.criteria && (
                        <div className="text-sm text-orange-800 dark:text-orange-300 bg-white/50 dark:bg-gray-800/50 p-3 rounded-lg">
                          <strong className="block mb-1">Критерии оценки:</strong>
                          <p className="whitespace-pre-wrap">{seminar.criteria}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {content.content?.work_programs && content.content.work_programs.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
                <div className="flex items-center gap-2 text-sm font-bold text-teal-600 dark:text-teal-400 uppercase tracking-widest mb-4">
                  <BookOpen className="w-5 h-5" /> Рабочие программы
                </div>
                <div className="space-y-4">
                  {content.content.work_programs.map((wp, idx) => (
                    <div key={idx} className="border-l-4 border-teal-400 pl-4 py-1">
                      <h4 className="font-bold text-gray-800 dark:text-gray-200 text-lg mb-1">{wp.module_title}</h4>
                      {wp.description && <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{wp.description}</p>}
                      {wp.topics && wp.topics.length > 0 && (
                        <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400 space-y-1">
                          {wp.topics.map((t, i) => <li key={i}>{t}</li>)}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {content.content?.bibliography && content.content.bibliography.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
                <div className="flex items-center gap-2 text-sm font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest mb-4">
                  <Library className="w-5 h-5" /> Библиография
                </div>
                <ul className="space-y-2 text-sm">
                  {content.content.bibliography.map((book, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-gray-700 dark:text-gray-300">
                      <span className="text-indigo-500 font-bold mt-0.5">[{idx + 1}]</span>
                      <span>{typeof book === 'string' ? book : JSON.stringify(book)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {content.content?.lectures?.modules_plan && content.content.lectures.modules_plan.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
                <div className="flex items-center gap-2 text-sm font-bold text-purple-600 dark:text-purple-400 uppercase tracking-widest mb-4">
                  <BookOpen className="w-5 h-5" /> Планы лекций
                </div>
                <div className="space-y-4">
                  {content.content.lectures.modules_plan.map((mod, idx) => (
                    <div key={idx} className="border-l-4 border-purple-400 pl-4 py-1">
                      <h4 className="font-bold text-gray-800 dark:text-gray-200 text-lg mb-2">{mod.module_title}</h4>
                      <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400 space-y-1">
                        {mod.theses?.map((thesis, i) => <li key={i}>{thesis}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><Download className="w-5 h-5"/> Экспорт материалов</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <button onClick={() => handleDownload('docx')} className="flex items-center justify-center gap-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 py-3 rounded-xl font-bold hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 transition-all">
                  <FileDown className="w-5 h-5 text-blue-600" /> Word
                </button>
                <button onClick={() => handleDownload('pptx')} className="flex items-center justify-center gap-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 py-3 rounded-xl font-bold hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 transition-all">
                  <Presentation className="w-5 h-5 text-orange-600" /> Презентация
                </button>
                <button onClick={() => handleDownload('lms')} className="flex items-center justify-center gap-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 py-3 rounded-xl font-bold hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 transition-all">
                  <Download className="w-5 h-5 text-purple-600" /> LMS (GIFT)
                </button>
                <button onClick={() => handleDownload('moodle')} className="flex items-center justify-center gap-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 py-3 rounded-xl font-bold hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 transition-all">
                  <FileDown className="w-5 h-5 text-red-600" /> Moodle XML
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
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500
        ${done ? 'bg-green-500 text-white shadow-lg shadow-green-500/30' 
          : active ? 'bg-blue-600 text-white ring-4 ring-blue-500/20 shadow-lg shadow-blue-500/30' 
          : 'bg-gray-200 dark:bg-gray-800 text-gray-500'}`}>
        {done ? <CheckCircle2 className="w-4 h-4" /> : num}
      </div>
      <span className={`font-bold text-sm hidden sm:block ${active ? 'text-blue-600 dark:text-blue-400' : done ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-600'}`}>
        {label}
      </span>
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