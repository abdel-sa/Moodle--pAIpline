import { useState } from 'react';
import { X, Plus, Trash2, Check, ArrowUpDown } from 'lucide-react';
import type { Question, QuestionType, Answer, MatchingPair, TestCase, OrderingItem } from '../types/course';

// â”€â”€â”€ Labels for all question types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  // New rich types
  'single_choice':          'Single Choice (eine richtige Antwort)',
  'true_false':             'Wahr / Falsch',
  'open_text':              'Offene Frage (Freitext, kein Auto-Grading)',
  'ordering':               'Reihenfolge (Elemente sortieren)',
  'fill_in_the_blank':      'LÃ¼ckentext (_____ als Platzhalter)',
  'calculation':            'Rechenaufgabe (mit LÃ¶sungsweg)',
  'reflection':             'Reflexionsfrage (kein Auto-Grading)',
  'file_upload_placeholder': 'Datei-Abgabe (Platzhalter)',
  // Legacy types
  'multiple-choice':  'Multiple Choice (eine richtige Antwort) [legacy]',
  'oumultiresponse':  'Multiple Response (mehrere Antworten mÃ¶glich)',
  'matching':         'Zuordnung (Paare zuordnen)',
  'numerical':        'Numerisch (Zahlenwert)',
  'coderunner':       'CodeRunner (Programmieraufgabe)',
  'shortanswer':      'Kurzantwort (freier Text) [legacy]',
};

const PREFERRED_TYPES: QuestionType[] = [
  'single_choice', 'true_false', 'open_text', 'ordering',
  'fill_in_the_blank', 'calculation', 'reflection', 'file_upload_placeholder',
  'coderunner', 'matching', 'oumultiresponse', 'numerical', 'multiple-choice', 'shortanswer',
];

// â”€â”€â”€ Props â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface Props {
  question: Question | null; // null = neue Frage erstellen
  onSave: (question: Question) => void;
  onCancel: () => void;
}

// â”€â”€â”€ Helper: random short ID â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function genId(): string {
  return Math.random().toString(36).substring(2, 10);
}

// â”€â”€â”€ Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function QuestionEditor({ question, onSave, onCancel }: Props) {
  // Common fields
  const [qType, setQType] = useState<QuestionType>(question?.questionType ?? 'single_choice');
  const [qText, setQText] = useState(question?.question ?? '');
  const [explanation, setExplanation] = useState(question?.explanation ?? '');

  // â”€â”€ single_choice / multiple-choice / oumultiresponse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [answers, setAnswers] = useState<Answer[]>(
    question?.answers ?? [
      { id: genId(), text: '', isCorrect: true,  explanation: '' },
      { id: genId(), text: '', isCorrect: false, explanation: '' },
      { id: genId(), text: '', isCorrect: false, explanation: '' },
    ]
  );

  // â”€â”€ true_false â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [isTrue, setIsTrue] = useState<boolean>(question?.isTrue ?? true);

  // â”€â”€ open_text / reflection / file_upload_placeholder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [sampleAnswer, setSampleAnswer] = useState(question?.sampleAnswer ?? '');

  // â”€â”€ matching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [matchingPairs, setMatchingPairs] = useState<MatchingPair[]>(
    question?.matchingPairs ?? [
      { id: genId(), left: '', right: '' },
      { id: genId(), left: '', right: '' },
    ]
  );

  // â”€â”€ numerical / calculation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [correctNumber, setCorrectNumber] = useState(question?.correctNumber?.toString() ?? '');
  const [tolerance,     setTolerance]     = useState(question?.tolerance?.toString() ?? '0');
  const [numberUnit,    setNumberUnit]    = useState(question?.numberUnit ?? '');
  const [solutionSteps, setSolutionSteps] = useState(question?.solutionSteps ?? '');

  // â”€â”€ coderunner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [programmingLanguage, setProgrammingLanguage] = useState(question?.programmingLanguage ?? 'python');
  const [starterCode,   setStarterCode]   = useState(question?.starterCode ?? '');
  const [expectedOutput,setExpectedOutput]= useState(question?.expectedOutput ?? '');
  const [testCases,     setTestCases]     = useState<TestCase[]>(
    question?.testCases ?? [{ id: genId(), input: '', expectedOutput: '', description: '' }]
  );
  const [solution,      setSolution]      = useState(question?.solution ?? '');

  // â”€â”€ shortanswer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [correctAnswer, setCorrectAnswer] = useState(question?.correctAnswer ?? '');

  // â”€â”€ ordering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [orderItems, setOrderItems] = useState<OrderingItem[]>(
    question?.items ?? [
      { id: genId(), text: '', position: 1 },
      { id: genId(), text: '', position: 2 },
      { id: genId(), text: '', position: 3 },
    ]
  );

  // â”€â”€ fill_in_the_blank â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [textWithBlanks, setTextWithBlanks] = useState(question?.textWithBlanks ?? '');
  const [blanks, setBlanks] = useState<string[]>(question?.blanks ?? ['', '']);

  // â”€â”€â”€ Save handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const handleSave = () => {
    if (!qText.trim()) return;

    const base = {
      id: question?.id ?? genId(),
      questionType: qType,
      question: qText.trim(),
      explanation: explanation.trim() || undefined,
    };

    let saved: Question;
    switch (qType) {
      case 'single_choice':
      case 'multiple-choice':
      case 'oumultiresponse':
        saved = { ...base, answers: answers.filter(a => a.text.trim()) };
        break;
      case 'true_false':
        saved = { ...base, isTrue };
        break;
      case 'open_text':
      case 'reflection':
      case 'file_upload_placeholder':
        saved = { ...base, sampleAnswer: sampleAnswer.trim() || undefined };
        break;
      case 'matching':
        saved = { ...base, matchingPairs: matchingPairs.filter(p => p.left.trim() && p.right.trim()) };
        break;
      case 'numerical':
        saved = {
          ...base,
          correctNumber: parseFloat(correctNumber) || 0,
          tolerance:     parseFloat(tolerance) || 0,
          numberUnit:    numberUnit.trim() || undefined,
        };
        break;
      case 'calculation':
        saved = {
          ...base,
          correctNumber: parseFloat(correctNumber) || 0,
          tolerance:     parseFloat(tolerance) || 0,
          numberUnit:    numberUnit.trim() || undefined,
          solutionSteps: solutionSteps.trim() || undefined,
        };
        break;
      case 'coderunner':
        saved = {
          ...base,
          programmingLanguage,
          starterCode:    starterCode.trim(),
          expectedOutput: expectedOutput.trim() || undefined,
          testCases:      testCases.filter(tc => tc.input.trim() || tc.expectedOutput.trim()),
          solution:       solution.trim() || undefined,
        };
        break;
      case 'shortanswer':
        saved = { ...base, correctAnswer: correctAnswer.trim() };
        break;
      case 'ordering':
        saved = { ...base, items: orderItems.filter(i => i.text.trim()) };
        break;
      case 'fill_in_the_blank':
        saved = {
          ...base,
          textWithBlanks: textWithBlanks.trim(),
          blanks: blanks.filter(b => b.trim()),
        };
        break;
      default:
        saved = base;
    }
    onSave(saved);
  };

  // â”€â”€â”€ Answer helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const addAnswer    = () => setAnswers(p => [...p, { id: genId(), text: '', isCorrect: false, explanation: '' }]);
  const removeAnswer = (id: string) => setAnswers(p => p.filter(a => a.id !== id));
  const updateAnswer = (id: string, field: keyof Answer, value: string | boolean) =>
    setAnswers(p => p.map(a => a.id === id ? { ...a, [field]: value } : a));
  const setOnlyCorrect = (id: string) =>
    setAnswers(p => p.map(a => ({ ...a, isCorrect: a.id === id })));

  // â”€â”€â”€ Matching helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const addPair    = () => setMatchingPairs(p => [...p, { id: genId(), left: '', right: '' }]);
  const removePair = (id: string) => setMatchingPairs(p => p.filter(x => x.id !== id));
  const updatePair = (id: string, side: 'left' | 'right', value: string) =>
    setMatchingPairs(p => p.map(x => x.id === id ? { ...x, [side]: value } : x));

  // â”€â”€â”€ Test case helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const addTestCase    = () => setTestCases(p => [...p, { id: genId(), input: '', expectedOutput: '', description: '' }]);
  const removeTestCase = (id: string) => setTestCases(p => p.filter(t => t.id !== id));
  const updateTestCase = (id: string, field: keyof TestCase, value: string) =>
    setTestCases(p => p.map(t => t.id === id ? { ...t, [field]: value } : t));

  // â”€â”€â”€ Ordering helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const addOrderItem    = () => setOrderItems(p => [...p, { id: genId(), text: '', position: p.length + 1 }]);
  const removeOrderItem = (id: string) =>
    setOrderItems(p => p.filter(i => i.id !== id).map((i, idx) => ({ ...i, position: idx + 1 })));
  const updateOrderItem = (id: string, value: string) =>
    setOrderItems(p => p.map(i => i.id === id ? { ...i, text: value } : i));

  // â”€â”€â”€ Blanks helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const addBlank    = () => setBlanks(p => [...p, '']);
  const removeBlank = (idx: number) => setBlanks(p => p.filter((_, i) => i !== idx));
  const updateBlank = (idx: number, value: string) =>
    setBlanks(p => p.map((b, i) => i === idx ? value : b));

  // â”€â”€â”€ Shared input styles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const input     = 'w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-primary)] transition-colors';
  const inputMono = input + ' font-mono';
  const isChoiceType = qType === 'single_choice' || qType === 'multiple-choice' || qType === 'oumultiresponse';
  const isMulti      = qType === 'oumultiresponse';

  // â”€â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="glass rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-white/10 shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 flex-shrink-0">
          <h2 className="text-lg font-semibold">
            {question ? 'Frage bearbeiten' : 'Neue Frage hinzufÃ¼gen'}
          </h2>
          <button onClick={onCancel} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5">

          {/* Question type selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
              Fragetyp
            </label>
            <select value={qType} onChange={e => setQType(e.target.value as QuestionType)} className={input}>
              {PREFERRED_TYPES.map(t => (
                <option key={t} value={t}>{QUESTION_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </div>

          {/* Question text */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
              Fragetext <span className="text-[var(--color-error)]">*</span>
            </label>
            <textarea rows={3} value={qText} onChange={e => setQText(e.target.value)}
              className={input + ' resize-none'} placeholder="Fragetext eingeben..." />
          </div>

          {/* â”€â”€ Single / Multiple choice / oumultiresponse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {isChoiceType && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                AntwortmÃ¶glichkeiten
                {isMulti ? ' â€” mehrere richtige mÃ¶glich' : ' â€” genau eine richtige Antwort'}
              </label>
              <div className="space-y-2">
                {answers.map((ans, idx) => (
                  <div key={ans.id} className="flex items-start gap-2">
                    <button
                      onClick={() => isMulti ? updateAnswer(ans.id, 'isCorrect', !ans.isCorrect) : setOnlyCorrect(ans.id)}
                      title="Als richtig markieren"
                      className={`mt-2 flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                        ans.isCorrect ? 'border-[var(--color-success)] bg-[var(--color-success)]/20' : 'border-slate-600 hover:border-slate-400'
                      }`}
                    >
                      {ans.isCorrect && <Check className="w-3 h-3 text-[var(--color-success)]" />}
                    </button>
                    <div className="flex-1 space-y-1">
                      <input type="text" value={ans.text}
                        onChange={e => updateAnswer(ans.id, 'text', e.target.value)}
                        className={input} placeholder={`Antwort ${idx + 1}`} />
                      <input type="text" value={ans.explanation ?? ''}
                        onChange={e => updateAnswer(ans.id, 'explanation', e.target.value)}
                        className="w-full bg-slate-800/30 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none focus:border-[var(--color-primary)] transition-colors"
                        placeholder="ErklÃ¤rung (optional)" />
                    </div>
                    <button onClick={() => removeAnswer(ans.id)} disabled={answers.length <= 2}
                      className="mt-2 text-slate-500 hover:text-[var(--color-error)] disabled:opacity-30 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button onClick={addAnswer}
                className="mt-3 flex items-center gap-1 text-sm text-[var(--color-primary)] hover:text-[#c7d2fe] transition-colors">
                <Plus className="w-4 h-4" /> Antwort hinzufÃ¼gen
              </button>
            </div>
          )}

          {/* â”€â”€ True / False â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'true_false' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Richtige Antwort
              </label>
              <div className="flex gap-3">
                <button onClick={() => setIsTrue(true)}
                  className={`flex-1 py-3 rounded-xl border-2 font-semibold text-sm transition-all ${
                    isTrue ? 'border-[var(--color-success)] bg-[var(--color-success)]/20 text-[var(--color-success)]'
                           : 'border-slate-700 text-slate-400 hover:border-slate-500'
                  }`}>âœ“ Wahr</button>
                <button onClick={() => setIsTrue(false)}
                  className={`flex-1 py-3 rounded-xl border-2 font-semibold text-sm transition-all ${
                    !isTrue ? 'border-[var(--color-error)] bg-[var(--color-error)]/20 text-[var(--color-error)]'
                            : 'border-slate-700 text-slate-400 hover:border-slate-500'
                  }`}>âœ— Falsch</button>
              </div>
            </div>
          )}

          {/* â”€â”€ Open text / Reflection / File upload placeholder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {(qType === 'open_text' || qType === 'reflection' || qType === 'file_upload_placeholder') && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                Musterantwort / Hinweis (optional, nur fÃ¼r Lektoren)
              </label>
              <textarea rows={4} value={sampleAnswer} onChange={e => setSampleAnswer(e.target.value)}
                className={input + ' resize-none'}
                placeholder={qType === 'file_upload_placeholder' ? 'Beschreibung was abgegeben werden soll...' : 'Beispielantwort oder Leitfaden fÃ¼r die Bewertung...'} />
              {qType !== 'file_upload_placeholder' && (
                <p className="text-xs text-slate-500 mt-1">Diese Antwort wird nicht automatisch bewertet.</p>
              )}
            </div>
          )}

          {/* â”€â”€ Ordering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'ordering' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Elemente in richtiger Reihenfolge
              </label>
              <div className="space-y-2">
                {orderItems.map((item, idx) => (
                  <div key={item.id} className="flex items-center gap-2">
                    <span className="flex-shrink-0 w-7 h-7 rounded-full bg-slate-700 text-xs font-bold flex items-center justify-center text-slate-400">
                      {idx + 1}
                    </span>
                    <input type="text" value={item.text}
                      onChange={e => updateOrderItem(item.id, e.target.value)}
                      className={input} placeholder={`Element ${idx + 1}`} />
                    <button onClick={() => removeOrderItem(item.id)} disabled={orderItems.length <= 2}
                      className="text-slate-500 hover:text-[var(--color-error)] disabled:opacity-30 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button onClick={addOrderItem}
                className="mt-3 flex items-center gap-1 text-sm text-[var(--color-primary)] hover:text-[#c7d2fe] transition-colors">
                <Plus className="w-4 h-4" /> Element hinzufÃ¼gen
              </button>
              <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
                <ArrowUpDown className="w-3 h-3" />
                Dem Lernenden werden die Elemente in zufÃ¤lliger Reihenfolge angezeigt.
              </p>
            </div>
          )}

          {/* â”€â”€ Fill in the blank â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'fill_in_the_blank' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                  Text mit LÃ¼cken <span className="text-slate-500 font-normal">(_____ als Platzhalter)</span>
                </label>
                <textarea rows={3} value={textWithBlanks} onChange={e => setTextWithBlanks(e.target.value)}
                  className={input + ' resize-none'}
                  placeholder="Die _____ ist ein wichtiges Prinzip der _____." />
                <p className="text-xs text-slate-500 mt-1">
                  {(textWithBlanks.match(/_____/g) ?? []).length} LÃ¼cke(n) erkannt
                </p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                  Richtige Antworten (in Reihenfolge der LÃ¼cken)
                </label>
                <div className="space-y-2">
                  {blanks.map((blank, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 w-16 flex-shrink-0">LÃ¼cke {idx + 1}</span>
                      <input type="text" value={blank} onChange={e => updateBlank(idx, e.target.value)}
                        className={input} placeholder={`Antwort ${idx + 1}`} />
                      <button onClick={() => removeBlank(idx)} disabled={blanks.length <= 1}
                        className="text-slate-500 hover:text-[var(--color-error)] disabled:opacity-30 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
                <button onClick={addBlank}
                  className="mt-2 flex items-center gap-1 text-sm text-[var(--color-primary)] hover:text-[#c7d2fe] transition-colors">
                  <Plus className="w-4 h-4" /> LÃ¼cke hinzufÃ¼gen
                </button>
              </div>
            </div>
          )}

          {/* â”€â”€ Calculation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'calculation' && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                    Richtiges Ergebnis <span className="text-[var(--color-error)]">*</span>
                  </label>
                  <input type="number" step="any" value={correctNumber}
                    onChange={e => setCorrectNumber(e.target.value)} className={input} placeholder="42.5" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Toleranz (Â±)</label>
                  <input type="number" step="any" min="0" value={tolerance}
                    onChange={e => setTolerance(e.target.value)} className={input} placeholder="0" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Einheit</label>
                  <input type="text" value={numberUnit}
                    onChange={e => setNumberUnit(e.target.value)} className={input} placeholder="m, kg, %" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                  LÃ¶sungsweg (Schritt fÃ¼r Schritt)
                </label>
                <textarea rows={4} value={solutionSteps} onChange={e => setSolutionSteps(e.target.value)}
                  className={input + ' resize-y'}
                  placeholder={"Schritt 1: â€¦\nSchritt 2: â€¦\nErgebnis: â€¦"} />
              </div>
            </div>
          )}

          {/* â”€â”€ Matching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'matching' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Zuordnungspaare (Begriff â†’ Zuordnung)
              </label>
              <div className="space-y-2">
                {matchingPairs.map((pair, idx) => (
                  <div key={pair.id} className="flex items-center gap-2">
                    <input type="text" value={pair.left} onChange={e => updatePair(pair.id, 'left', e.target.value)}
                      className={input} placeholder={`Begriff ${idx + 1}`} />
                    <span className="text-slate-500 flex-shrink-0">â†’</span>
                    <input type="text" value={pair.right} onChange={e => updatePair(pair.id, 'right', e.target.value)}
                      className={input} placeholder={`Zuordnung ${idx + 1}`} />
                    <button onClick={() => removePair(pair.id)} disabled={matchingPairs.length <= 2}
                      className="text-slate-500 hover:text-[var(--color-error)] disabled:opacity-30 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button onClick={addPair}
                className="mt-3 flex items-center gap-1 text-sm text-[var(--color-primary)] hover:text-[#c7d2fe] transition-colors">
                <Plus className="w-4 h-4" /> Paar hinzufÃ¼gen
              </button>
            </div>
          )}

          {/* â”€â”€ Numerical â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'numerical' && (
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                  Richtige Antwort <span className="text-[var(--color-error)]">*</span>
                </label>
                <input type="number" step="any" value={correctNumber}
                  onChange={e => setCorrectNumber(e.target.value)} className={input} placeholder="42" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Toleranz (Â±)</label>
                <input type="number" step="any" min="0" value={tolerance}
                  onChange={e => setTolerance(e.target.value)} className={input} placeholder="0" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Einheit</label>
                <input type="text" value={numberUnit}
                  onChange={e => setNumberUnit(e.target.value)} className={input} placeholder="cm, kg, %" />
              </div>
            </div>
          )}

          {/* â”€â”€ CodeRunner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'coderunner' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Programmiersprache</label>
                <select value={programmingLanguage} onChange={e => setProgrammingLanguage(e.target.value)} className={input}>
                  <option value="python">Python</option>
                  <option value="javascript">JavaScript</option>
                  <option value="java">Java</option>
                  <option value="sql">SQL</option>
                  <option value="c">C</option>
                  <option value="cpp">C++</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                  Starter-Code (Template fÃ¼r Studierende)
                </label>
                <textarea rows={6} value={starterCode} onChange={e => setStarterCode(e.target.value)}
                  className={inputMono + ' resize-y'}
                  placeholder="# Code-Template, das Studierende vervollstÃ¤ndigen mÃ¼ssen" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">MusterlÃ¶sung</label>
                <textarea rows={5} value={solution} onChange={e => setSolution(e.target.value)}
                  className={inputMono + ' resize-y'}
                  placeholder="# Korrekte LÃ¶sung (nur fÃ¼r Lektoren sichtbar)" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">TestfÃ¤lle</label>
                <div className="space-y-2">
                  {testCases.map((tc, idx) => (
                    <div key={tc.id} className="bg-slate-800/30 rounded-xl p-3 space-y-2 border border-slate-700/30">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-400 font-medium">Testfall {idx + 1}</span>
                        <button onClick={() => removeTestCase(tc.id)} disabled={testCases.length <= 1}
                          className="text-slate-500 hover:text-[var(--color-error)] disabled:opacity-30 transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      <input type="text" value={tc.description ?? ''}
                        onChange={e => updateTestCase(tc.id, 'description', e.target.value)}
                        className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-[var(--color-primary)]"
                        placeholder="Beschreibung (optional)" />
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Eingabe / Aufruf</p>
                          <input type="text" value={tc.input}
                            onChange={e => updateTestCase(tc.id, 'input', e.target.value)}
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-[var(--color-primary)]"
                            placeholder="solve(5)" />
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Erwartete Ausgabe</p>
                          <input type="text" value={tc.expectedOutput}
                            onChange={e => updateTestCase(tc.id, 'expectedOutput', e.target.value)}
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-[var(--color-primary)]"
                            placeholder="25" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <button onClick={addTestCase}
                  className="mt-2 flex items-center gap-1 text-sm text-[var(--color-primary)] hover:text-[#c7d2fe] transition-colors">
                  <Plus className="w-4 h-4" /> Testfall hinzufÃ¼gen
                </button>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                  Allgemeine Erwartungsbeschreibung
                </label>
                <input type="text" value={expectedOutput} onChange={e => setExpectedOutput(e.target.value)}
                  className={input} placeholder="z.B. Gibt einen float zurÃ¼ck" />
              </div>
            </div>
          )}

          {/* â”€â”€ Short answer (legacy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {qType === 'shortanswer' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                Richtige Antwort
              </label>
              <input type="text" value={correctAnswer} onChange={e => setCorrectAnswer(e.target.value)}
                className={input} placeholder="Erwartete Antwort des Lernenden" />
            </div>
          )}

          {/* Explanation (always visible) */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
              ErklÃ¤rung zur Antwort (optional)
            </label>
            <textarea rows={2} value={explanation} onChange={e => setExplanation(e.target.value)}
              className={input + ' resize-none'}
              placeholder="Wird dem Lernenden nach der Antwort angezeigt..." />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10 flex-shrink-0">
          <button onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-white/5 transition-colors">
            Abbrechen
          </button>
          <button onClick={handleSave} disabled={!qText.trim()}
            className="bg-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#c7d2fe] text-slate-900 font-semibold px-5 py-2 rounded-lg text-sm flex items-center gap-2 transition-all shadow-[0_0_16px_rgba(180,190,254,0.25)] disabled:shadow-none">
            <Check className="w-4 h-4" />
            Speichern
          </button>
        </div>
      </div>
    </div>
  );
}
