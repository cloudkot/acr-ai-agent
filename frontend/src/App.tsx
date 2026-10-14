import { useState, useEffect, useRef } from 'react';
import { api, type Artifacts } from './api';
import { Send, FileUp, Download, Loader2, Bot, User, CheckCircle2 } from 'lucide-react';
import { CompetenciesView, PlanView, TestsView, SeminarsView, SlidesView } from './components/ArtifactViews';

function App() {
  const [messages, setMessages] = useState<{role: 'user'|'ai', text: string}[]>([
    { role: 'ai', text: 'Привет! Я ИИ-агент для создания образовательных программ. Опишите, какую программу вам нужно разработать, и при необходимости загрузите референсы.' }
  ]);
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle'|'generating'|'done'>('idle');
  const [currentStep, setCurrentStep] = useState<string>('');
  const [artifacts, setArtifacts] = useState<Artifacts>({});
  const [activeTab, setActiveTab] = useState<'competencies'|'plan'|'tests'|'seminars'|'slides'>('competencies');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Автоскролл чата
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Поллинг статуса
  useEffect(() => {
    let interval: any;
    if (taskId && status === 'generating') {
      interval = setInterval(async () => {
        try {
          const res = await api.getStatus(taskId);
          setCurrentStep(res.current_step);
          if (res.artifacts) setArtifacts(res.artifacts);
          
          if (res.status === 'completed') {
            setStatus('done');
            setMessages(prev => {
   
              const alreadyExists = prev.some(m => m.text.includes('Генерация завершена'));
              if (alreadyExists) return prev;
            return [...prev, { role: 'ai', text: 'Генерация завершена! Проверьте артефакты справа. Вы можете точечно доработать любой элемент.' }];
          });
          clearInterval(interval);
        }
        } catch (e) {
          console.error(e);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, status]);

  const handleSend = async () => {
    if (!input.trim() || status === 'generating') return;
    
    const userMessage = input;
    setMessages(prev => [...prev, { role: 'user', text: userMessage }]);
    setInput('');
    setStatus('generating');
    setCurrentStep('Инициализация...');
    
    try {
      // В реальном приложении здесь нужно извлекать часы и направление из текста, 
      // либо добавлять отдельные поля в UI. Для хакатона хардкодим.
      const res = await api.startGeneration(
        { prompt: userMessage, hours: 72, direction: 'IT' }, 
        files
      );
      setTaskId(res.task_id);
      setMessages(prev => [...prev, { role: 'ai', text: 'Запускаю пайплайн генерации. Это может занять несколько минут...' }]);
    } catch (e) {
      setStatus('idle');
      setMessages(prev => [...prev, { role: 'ai', text: 'Ошибка запуска генерации. Проверьте бэкенд.' }]);
    }
  };

  const handleExport = async () => {
    if (!taskId) return;
    await api.exportDocx(taskId);
  };

  const handleRefine = async (itemId: string, instruction: string) => {
    if (!taskId || !instruction.trim()) return;
    setMessages(prev => [...prev, { role: 'user', text: `Правка для элемента ${itemId}: ${instruction}` }]);
    await api.refineItem(taskId, activeTab, itemId, instruction);
    setMessages(prev => [...prev, { role: 'ai', text: `Элемент обновлен!` }]);
    // В реальном приложении здесь нужно обновить конкретный артефакт в стейте
  };

  const steps = [
    { id: 'analysis', label: 'Анализ' },
    { id: 'competencies', label: 'Компетенции' },
    { id: 'plan', label: 'План' },
    { id: 'tests', label: 'Тесты' },
    { id: 'slides', label: 'Слайды' },
  ];

  const currentStepIndex = steps.findIndex(s => currentStep.toLowerCase().includes(s.label.toLowerCase()));

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 font-sans overflow-hidden">
      
      {/* ЛЕВАЯ КОЛОНКА: ЧАТ */}
      <div className="w-1/3 flex flex-col border-r border-gray-200 bg-white shadow-sm z-10">
        <div className="p-4 border-b bg-white flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
            <Bot className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <div className="font-bold text-sm">ИИ-Агент АЦР</div>
            <div className="text-xs text-green-500 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500"></span> Online
            </div>
          </div>
        </div>
        
        {/* Лента сообщений */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/50">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
                {m.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              <div className={`p-3 rounded-lg max-w-[85%] text-sm ${m.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white border rounded-tl-none shadow-sm'}`}>
                {m.text}
              </div>
            </div>
          ))}
          {status === 'generating' && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-gray-600" />
              </div>
              <div className="p-3 rounded-lg bg-white border rounded-tl-none shadow-sm flex items-center gap-2 text-sm text-blue-600">
                <Loader2 className="animate-spin w-4 h-4" />
                <span>Этап: {currentStep || 'Анализ...'}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Ввод */}
        <div className="p-4 border-t bg-white space-y-3">
          <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer hover:text-blue-600 transition-colors bg-gray-50 p-2 rounded border border-dashed border-gray-300">
            <FileUp className="w-4 h-4" />
            <span>Прикрепить референсы (.docx, .pdf)</span>
            <input type="file" multiple className="hidden" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
          </label>
          {files.length > 0 && (
            <div className="text-xs text-green-600 bg-green-50 p-2 rounded flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Загружено файлов: {files.length}
            </div>
          )}
          
          <div className="flex gap-2">
            <input 
              value={input} 
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Опишите программу обучения..." 
              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
              disabled={status === 'generating'}
            />
            <button 
              onClick={handleSend} 
              disabled={status === 'generating' || !input.trim()} 
              className="bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* ЦЕНТРАЛЬНАЯ КОЛОНКА: АРТЕФАКТЫ */}
      <div className="flex-1 flex flex-col bg-white">
        
        {/* Прогресс-бар (Stepper) */}
        {status !== 'idle' && (
          <div className="bg-white border-b px-6 py-3 flex items-center justify-between text-xs font-medium text-gray-500">
            {steps.map((step, idx) => {
              const isActive = idx === currentStepIndex;
              const isDone = idx < currentStepIndex || status === 'done';
              return (
                <div key={step.id} className="flex items-center gap-2">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center ${isDone ? 'bg-green-500 text-white' : isActive ? 'bg-blue-600 text-white animate-pulse' : 'bg-gray-200'}`}>
                    {isDone ? <CheckCircle2 className="w-3 h-3" /> : idx + 1}
                  </div>
                  <span className={isActive || isDone ? 'text-gray-900' : ''}>{step.label}</span>
                  {idx < steps.length - 1 && <div className={`w-8 h-0.5 ${isDone ? 'bg-green-500' : 'bg-gray-200'}`} />}
                </div>
              );
            })}
          </div>
        )}

        {status === 'done' ? (
          <>
            {/* Шапка с табами и экспортом */}
            <div className="p-4 border-b flex justify-between items-center bg-white sticky top-0 z-10">
              <div className="flex gap-1 overflow-x-auto bg-gray-100 p-1 rounded-lg">
                {[
                  { id: 'competencies', label: 'Карта компетенций' },
                  { id: 'plan', label: 'Учебный план' },
                  { id: 'tests', label: 'Тесты' },
                  { id: 'seminars', label: 'Семинары' },
                  { id: 'slides', label: 'Слайды' }
                ].map((tab) => (
                  <button 
                    key={tab.id} 
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`px-4 py-1.5 text-sm rounded-md transition-all ${activeTab === tab.id ? 'bg-white text-blue-700 shadow-sm font-semibold' : 'text-gray-500 hover:text-gray-900'}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <button onClick={handleExport} className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 shadow-sm transition-colors font-medium">
                <Download className="w-4 h-4" /> Экспорт DOCX
              </button>
            </div>

            {/* Контент таба */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
              <div className="max-w-5xl mx-auto">
                {activeTab === 'competencies' && <CompetenciesView data={artifacts.competencies || []} />}
                {activeTab === 'plan' && <PlanView data={artifacts.plan || []} />}
                {activeTab === 'tests' && <TestsView data={artifacts.tests || []} taskId={taskId!} onRefine={handleRefine} />}
                {activeTab === 'seminars' && <SeminarsView data={artifacts.seminars || []} />}
                {activeTab === 'slides' && <SlidesView data={artifacts.slides || []} />}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400 bg-gray-50">
            <div className="w-20 h-20 bg-gray-200 rounded-full flex items-center justify-center mb-6">
              <Bot className="w-10 h-10 text-gray-400" />
            </div>
            <h2 className="text-xl font-semibold text-gray-600 mb-2">Ожидание запроса</h2>
            <p className="text-sm max-w-md text-center">Опишите требования к программе в чате слева, и агент сгенерирует полный комплект материалов.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;