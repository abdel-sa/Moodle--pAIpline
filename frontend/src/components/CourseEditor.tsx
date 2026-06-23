import React, { useState, useEffect, useCallback } from 'react';
import {
  BookOpen, Plus, Trash2, Edit2, Save, X, ChevronRight,
  Clock, Target, Code, HelpCircle, GraduationCap,
  ChevronDown, ChevronUp, RefreshCw, AlertCircle, Check,
  FileText as _FileText, Lightbulb, ClipboardList, MessageSquare, Home,
  Download,
} from 'lucide-react';
import axios from 'axios';
import type { Course, TeachingUnit, Question, CourseListItem, QuestionType } from '../types/course';
import QuestionEditor from './QuestionEditor';

const API_BASE = 'http://localhost:8000/api';

// ─── Display metadata for question types ─────────────────────────────────────

const Q_LABELS: Record<QuestionType, string> = {
  'single_choice':          'Single Choice',
  'true_false':             'Wahr/Falsch',
  'open_text':              'Offene Frage',
  'ordering':               'Reihenfolge',
  'fill_in_the_blank':      'Lückentext',
  'calculation':            'Rechenaufgabe',
  'reflection':             'Reflexion',
  'file_upload_placeholder': 'Datei-Abgabe',
  'multiple-choice': 'Multiple Choice',
  'oumultiresponse': 'Multi-Response',
  'matching':        'Zuordnung',
  'numerical':       'Numerisch',
  'coderunner':      'CodeRunner',
  'shortanswer':     'Kurzantwort',
};

const Q_COLORS: Record<QuestionType, string> = {
  'single_choice':          'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'true_false':             'bg-teal-500/20 text-teal-300 border-teal-500/30',
  'open_text':              'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  'ordering':               'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'fill_in_the_blank':      'bg-violet-500/20 text-violet-300 border-violet-500/30',
  'calculation':            'bg-lime-500/20 text-lime-300 border-lime-500/30',
  'reflection':             'bg-rose-500/20 text-rose-300 border-rose-500/30',
  'file_upload_placeholder': 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  'multiple-choice': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'oumultiresponse': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  'matching':        'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  'numerical':       'bg-green-500/20 text-green-300 border-green-500/30',
  'coderunner':      'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'shortanswer':     'bg-pink-500/20 text-pink-300 border-pink-500/30',
};

// ─── Shared input style ───────────────────────────────────────────────────────

const inputCls = 'w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-primary)] transition-colors';

type AiProvider = 'ollama' | 'groq' | 'gemini' | 'cerebras';

interface CourseEditorProps {
  provider?: AiProvider;
  model?: string;
  groqApiKey?: string;
  geminiApiKey?: string;
  cerebrasApiKey?: string;
  detail?: 'compact' | 'normal' | 'detailed';
  language?: 'de' | 'en';
}

// ─── Small random ID helper ───────────────────────────────────────────────────

function genId(): string {
  return Math.random().toString(36).substring(2, 10);
}

function normalizeCourse(course: Course): Course {
  return {
    ...course,
    units: (course.units ?? []).map(unit => ({
      ...unit,
      description: unit.description ?? '',
      learningObjectives: unit.learningObjectives ?? [],
      theoryContent: unit.theoryContent ?? '',
      estimatedDuration: unit.estimatedDuration ?? 60,
      questions: unit.questions ?? [],
      materials: unit.materials ?? [],
    })),
  };
}

// ─── Summary text for a collapsed question card ───────────────────────────────

function questionSummary(q: Question): string {
  switch (q.questionType) {
    case 'single_choice':
    case 'multiple-choice':
    case 'oumultiresponse':
      return `${q.answers?.length ?? 0} Antwortmöglichkeiten`;
    case 'true_false':
      return q.isTrue !== undefined ? (q.isTrue ? 'Richtig: Wahr' : 'Richtig: Falsch') : 'Wahr / Falsch';
    case 'matching':
      return `${q.matchingPairs?.length ?? 0} Paare`;
    case 'numerical':
      return `Antwort: ${q.correctNumber ?? '?'}${q.numberUnit ? ' ' + q.numberUnit : ''}${q.tolerance ? ' ±' + q.tolerance : ''}`;
    case 'calculation':
      return `Ergebnis: ${q.correctNumber ?? '?'}${q.numberUnit ? ' ' + q.numberUnit : ''}${q.solutionSteps ? ' · mit Lösungsweg' : ''}`;
    case 'coderunner':
      return `${q.programmingLanguage} · ${q.testCases?.length ?? 0} Testfälle`;
    case 'shortanswer':
      return `Antwort: "${q.correctAnswer ?? ''}"`;
    case 'ordering':
      return `${q.items?.length ?? 0} Elemente sortieren`;
    case 'fill_in_the_blank':
      return `${q.blanks?.length ?? 0} Lücke(n)`;
    case 'open_text':
    case 'reflection':
      return q.sampleAnswer ? 'Mit Musterantwort' : 'Freie Antwort';
    case 'file_upload_placeholder':
      return 'Datei-Abgabe';
    default:
      return '';
  }
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function CourseEditor({
  provider = 'gemini',
  model = '',
  groqApiKey = '',
  geminiApiKey = '',
  cerebrasApiKey = '',
  detail = 'compact',
  language = 'de',
}: CourseEditorProps) {
  const [courses, setCourses]               = useState<CourseListItem[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<Course | null>(null);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);

  // Unit edit state
  const [isEditingUnit, setIsEditingUnit] = useState(false);
  const [editingUnit,   setEditingUnit]   = useState<TeachingUnit | null>(null);
  const [newObjective,  setNewObjective]  = useState('');

  // Question editor modal
  const [qEditorState, setQEditorState] = useState<{
    question: Question | null; // null = new question
    unitId: string;
    blockId?: string;          // if editing inside a contentBlock
  } | null>(null);

  const [loading, setLoading] = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [generatingUnitId, setGeneratingUnitId] = useState<string | null>(null);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingElapsed, setGeneratingElapsed] = useState(0);
  const [generatingStatus, setGeneratingStatus] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const [error,   setError]   = useState<string | null>(null);

  // Elapsed timer during generation
  useEffect(() => {
    if (!generatingUnitId) { setGeneratingElapsed(0); return; }
    setGeneratingElapsed(0);
    const t = setInterval(() => setGeneratingElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [generatingUnitId]);

  // ─── Derived ─────────────────────────────────────────────────────────────────

  const selectedUnit = selectedCourse?.units.find(u => u.id === selectedUnitId) ?? null;
  const generatedUnitCount = selectedCourse?.units.filter(u => u.contentBlocks && u.contentBlocks.length > 0).length ?? 0;

  // ─── Data fetching ────────────────────────────────────────────────────────────

  const loadCourses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<CourseListItem[]>(`${API_BASE}/courses`);
      setCourses(res.data);
    } catch {
      setError('Kursliste konnte nicht geladen werden. Ist der Server erreichbar?');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCourse = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    setExportUrl(null);
    try {
      const res = await axios.get<Course>(`${API_BASE}/courses/${id}`);
      const course = normalizeCourse(res.data);
      setSelectedCourse(course);
      setSelectedUnitId(course.units[0]?.id ?? null);
      setIsEditingUnit(false);
      setEditingUnit(null);
    } catch {
      setError('Kurs konnte nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }, []);

  /** Persist the full course to the backend and refresh local state. */
  const persistCourse = useCallback(async (course: Course): Promise<Course | null> => {
    setSaving(true);
    try {
      const res = await axios.put<Course>(`${API_BASE}/courses/${course.id}`, course);
      const saved = normalizeCourse(res.data);
      setSelectedCourse(saved);
      return saved;
    } catch {
      setError('Speichern fehlgeschlagen.');
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  useEffect(() => { loadCourses(); }, [loadCourses]);

  // ─── Unit CRUD ────────────────────────────────────────────────────────────────

  const startEditUnit = () => {
    if (!selectedUnit) return;
    // Deep-copy so edits don't immediately mutate the displayed unit
    setEditingUnit(JSON.parse(JSON.stringify(selectedUnit)));
    setIsEditingUnit(true);
    setNewObjective('');
  };

  const cancelEditUnit = () => {
    setIsEditingUnit(false);
    setEditingUnit(null);
    setNewObjective('');
  };

  const saveUnit = async () => {
    if (!selectedCourse || !editingUnit) return;
    const updatedUnits = selectedCourse.units.map(u =>
      u.id === editingUnit.id ? editingUnit : u
    );
    const updated = await persistCourse({ ...selectedCourse, units: updatedUnits });
    if (updated) { cancelEditUnit(); }
  };

  const generateUnit = async (unitId: string) => {
    if (!selectedCourse) return;
    setGeneratingUnitId(unitId);
    setError(null);
    try {
      const res = await axios.post<Course>(
        `${API_BASE}/courses/${selectedCourse.id}/generate-unit/${unitId}`,
        {
          provider,
          model,
          groq_api_key: groqApiKey,
          gemini_api_key: geminiApiKey,
          cerebras_api_key: cerebrasApiKey,
          detail: selectedCourse.detailLevel ?? detail,
          language: selectedCourse.language ?? language,
        }
      );
      setSelectedCourse(normalizeCourse(res.data));
      setSelectedUnitId(unitId);
      await loadCourses();
    } catch (e: any) {
      setError(e?.response?.data?.message ?? 'Einheit konnte nicht generiert werden.');
    } finally {
      setGeneratingUnitId(null);
    }
  };

  const generateNextUnit = async () => {
    const next = selectedCourse?.units.find(u => !(u.contentBlocks && u.contentBlocks.length > 0));
    if (next) {
      setSelectedUnitId(next.id);
      await generateUnit(next.id);
    }
  };

  const generateAllUnits = async () => {
    if (!selectedCourse) return;
    const pending = selectedCourse.units.filter(u => !(u.contentBlocks && u.contentBlocks.length > 0));
    if (pending.length === 0) return;

    setGeneratingAll(true);
    setError(null);
    let failCount = 0;

    for (let i = 0; i < pending.length; i++) {
      const unit = pending[i];
      setGeneratingUnitId(unit.id);
      setSelectedUnitId(unit.id);
      setGeneratingStatus(`Einheit ${i + 1}/${pending.length}: ${unit.title}`);
      try {
        const res = await axios.post<Course>(
          `${API_BASE}/courses/${selectedCourse.id}/generate-unit/${unit.id}`,
          {
            provider,
            model,
            groq_api_key: groqApiKey,
            gemini_api_key: geminiApiKey,
            cerebras_api_key: cerebrasApiKey,
            detail: selectedCourse.detailLevel ?? detail,
            language: selectedCourse.language ?? language,
          }
        );
        setSelectedCourse(normalizeCourse(res.data));
      } catch {
        failCount++;
      }
      // Kurze Pause zwischen Einheiten um API Rate-Limits zu vermeiden
      await new Promise(r => setTimeout(r, 2000));
    }

    setGeneratingUnitId(null);
    setGeneratingAll(false);
    setGeneratingStatus('');
    await loadCourses();
    if (failCount > 0) {
      setError(`${failCount} Einheit(en) konnten nicht generiert werden. Klicke "Alle generieren" erneut um es zu wiederholen.`);
    }
  };

  const exportMoodleBackup = async () => {
    if (!selectedCourse) return;
    setExporting(true);
    setExportUrl(null);
    setError(null);
    try {
      await persistCourse(selectedCourse);
      const res = await axios.post<{ filename: string; download_url: string }>(
        `${API_BASE}/courses/${selectedCourse.id}/export-mbz`
      );
      const apiHost = API_BASE.replace(/\/api$/, '');
      setExportUrl(`${apiHost}${res.data.download_url}`);
    } catch (e: any) {
      setError(e?.response?.data?.message ?? 'Moodle-Backup konnte nicht erstellt werden.');
    } finally {
      setExporting(false);
    }
  };

  const addUnit = async () => {
    if (!selectedCourse) return;
    const newUnit: TeachingUnit = {
      id:                genId(),
      title:             'Neue Unterrichtseinheit',
      description:       '',
      learningObjectives: [],
      theoryContent:     '',
      estimatedDuration: 60,
      questions:         [],
    };
    const updated = await persistCourse({
      ...selectedCourse,
      units: [...selectedCourse.units, newUnit],
    });
    if (updated) { setSelectedUnitId(newUnit.id); }
  };

  const deleteUnit = async (unitId: string) => {
    if (!selectedCourse) return;
    if (!window.confirm('Einheit wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.')) return;
    const updatedUnits = selectedCourse.units.filter(u => u.id !== unitId);
    const updated = await persistCourse({ ...selectedCourse, units: updatedUnits });
    if (updated) { setSelectedUnitId(updatedUnits[0]?.id ?? null); }
  };

  // ─── Question CRUD ────────────────────────────────────────────────────────────

  const openAddQuestion = (blockId?: string) => {
    if (!selectedUnitId) return;
    setQEditorState({ question: null, unitId: selectedUnitId, blockId });
  };

  const openEditQuestion = (q: Question, blockId?: string) => {
    if (!selectedUnitId) return;
    setQEditorState({ question: q, unitId: selectedUnitId, blockId });
  };

  const deleteQuestion = async (questionId: string) => {
    if (!selectedCourse || !selectedUnitId) return;
    if (!window.confirm('Frage wirklich löschen?')) return;
    const updatedUnits = selectedCourse.units.map(u => {
      if (u.id !== selectedUnitId) return u;
      // Remove from flat questions
      const newQuestions = u.questions.filter(q => q.id !== questionId);
      // Remove from contentBlocks quiz blocks too
      const newBlocks = u.contentBlocks?.map(b =>
        b.type === 'quiz' && b.questions
          ? { ...b, questions: b.questions.filter(q => q.id !== questionId) }
          : b
      );
      return { ...u, questions: newQuestions, contentBlocks: newBlocks };
    });
    await persistCourse({ ...selectedCourse, units: updatedUnits });
  };

  const handleQuestionSave = async (question: Question) => {
    if (!selectedCourse || !qEditorState) return;
    const { unitId, blockId } = qEditorState;
    const updatedUnits = selectedCourse.units.map(u => {
      if (u.id !== unitId) return u;
      if (blockId && u.contentBlocks) {
        // Update inside a contentBlock's quiz questions
        const updatedBlocks = u.contentBlocks.map(block => {
          if (block.id !== blockId) return block;
          const exists = block.questions?.some(q => q.id === question.id);
          const updatedQs = exists
            ? block.questions!.map(q => q.id === question.id ? question : q)
            : [...(block.questions ?? []), question];
          return { ...block, questions: updatedQs };
        });
        // Sync flat questions array from all quiz blocks
        const allBlockQs = updatedBlocks
          .filter(b => b.type === 'quiz')
          .flatMap(b => b.questions ?? []);
        return { ...u, contentBlocks: updatedBlocks, questions: allBlockQs };
      } else {
        // Flat questions array
        const exists = u.questions.some(q => q.id === question.id);
        const updatedQs = exists
          ? u.questions.map(q => q.id === question.id ? question : q)
          : [...u.questions, question];
        return { ...u, questions: updatedQs };
      }
    });
    const updated = await persistCourse({ ...selectedCourse, units: updatedUnits });
    if (updated) { setQEditorState(null); }
  };

  // ─── Helper: switch to a unit (close edit mode) ───────────────────────────────

  const selectUnit = (id: string) => {
    setSelectedUnitId(id);
    setIsEditingUnit(false);
    setEditingUnit(null);
  };

  // ─── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-5">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <GraduationCap className="w-6 h-6 text-[var(--color-primary)]" />
          <h2 className="text-xl font-semibold">Kurs-Editor</h2>
          {selectedCourse && (
            <span className="text-sm text-slate-400">
              — {selectedCourse.title} · {generatedUnitCount}/{selectedCourse.units.length} generiert
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {selectedCourse && (
            <>
              <button
                onClick={exportMoodleBackup}
                disabled={exporting || saving}
                className="bg-[var(--color-success)]/20 hover:bg-[var(--color-success)]/30 text-[var(--color-success)] border border-[var(--color-success)]/30 px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                {exporting ? 'Erstelle MBZ...' : 'Moodle-Backup'}
              </button>
              {exportUrl && (
                <a
                  href={exportUrl}
                  download
                  className="bg-[var(--color-success)] hover:bg-[#bbf7d0] text-slate-900 font-semibold px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Download
                </a>
              )}
            </>
          )}
          {selectedCourse && generatedUnitCount < selectedCourse.units.length && (
            <>
              <button
                onClick={generateAllUnits}
                disabled={!!generatingUnitId || generatingAll}
                className="bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/80 text-slate-900 font-semibold px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${generatingAll ? 'animate-spin' : ''}`} />
                {generatingAll
                  ? `Generiere ${generatingUnitId ? selectedCourse.units.findIndex(u => u.id === generatingUnitId) + 1 : ''}/${selectedCourse.units.length}…`
                  : `Alle generieren (${selectedCourse.units.length - generatedUnitCount})`}
              </button>
              <button
                onClick={generateNextUnit}
                disabled={!!generatingUnitId || generatingAll}
                className="bg-[var(--color-primary)]/20 hover:bg-[var(--color-primary)]/30 text-[var(--color-primary)] border border-[var(--color-primary)]/30 px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${generatingUnitId && !generatingAll ? 'animate-spin' : ''}`} />
                Nächste offene Einheit
              </button>
            </>
          )}
          {courses.length > 0 && (
            <div className="flex items-center gap-1">
              <select
                value={selectedCourse?.id ?? ''}
                onChange={e => e.target.value && loadCourse(e.target.value)}
                className="bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-primary)] min-w-[220px]"
              >
                <option value="">— Kurs wählen —</option>
                {courses.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.generatedUnitCount ?? 0}/{c.unitCount} generiert)
                  </option>
                ))}
              </select>
              {selectedCourse && (
                <button
                  onClick={async () => {
                    if (!window.confirm(`Kurs "${selectedCourse.title}" wirklich löschen?`)) return;
                    try {
                      await axios.delete(`${API_BASE}/courses/${selectedCourse.id}`);
                      setSelectedCourse(null);
                      setSelectedUnitId(null);
                      setExportUrl(null);
                      await loadCourses();
                    } catch {
                      setError('Kurs konnte nicht gelöscht werden.');
                    }
                  }}
                  title="Kurs löschen"
                  className="p-2 rounded-lg text-slate-500 hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
          <button
            onClick={loadCourses}
            title="Kursliste neu laden"
            className="glass px-3 py-2 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Generation status bar ───────────────────────────────────────────── */}
      {generatingUnitId && (
        <div className="glass rounded-xl px-4 py-3 border border-[var(--color-primary)]/20 bg-[var(--color-primary)]/5 flex items-center gap-3">
          <RefreshCw className="w-4 h-4 text-[var(--color-primary)] animate-spin flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-200 truncate">
              {generatingStatus || `Generiere: ${selectedCourse?.units.find(u => u.id === generatingUnitId)?.title ?? generatingUnitId}`}
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {generatingElapsed < 15
                ? 'KI generiert Inhalte…'
                : generatingElapsed < 60
                  ? `Läuft seit ${generatingElapsed}s — bitte warten…`
                  : `Wartet auf API Rate-Limit Reset (${generatingElapsed}s) — nicht abbrechen!`}
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400 flex-shrink-0">{generatingElapsed}s</span>
        </div>
      )}

      {/* ── Error banner ─────────────────────────────────────────────────────── */}
      {error && (
        <div className="glass rounded-xl p-4 border border-[var(--color-error)]/30 bg-[var(--color-error)]/5 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-[var(--color-error)] flex-shrink-0" />
          <span className="text-sm text-[var(--color-error)] flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {selectedCourse?._warnings && selectedCourse._warnings.length > 0 && (
        <div className="glass rounded-xl p-4 border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/5">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-[var(--color-warning)]" />
            <span className="text-sm font-semibold text-[var(--color-warning)]">Qualitaetscheck</span>
          </div>
          <ul className="space-y-1">
            {selectedCourse._warnings.slice(0, 6).map((warning, idx) => (
              <li key={idx} className="text-xs text-slate-300">{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Empty state ──────────────────────────────────────────────────────── */}
      {!loading && !selectedCourse && (
        <div className="glass rounded-2xl p-12 text-center border border-white/5">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-300 mb-2">Kein Kurs ausgewählt</h3>
          <p className="text-slate-500 text-sm max-w-md mx-auto">
            {courses.length === 0
              ? 'Keine Kurse gefunden. Stelle sicher, dass der Server läuft und JSON-Dateien im courses/ Verzeichnis vorhanden sind.'
              : 'Wähle einen Kurs aus dem Dropdown oben.'}
          </p>
        </div>
      )}

      {/* ── Main two-column layout ───────────────────────────────────────────── */}
      {!loading && selectedCourse && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5" style={{ minHeight: 600 }}>

          {/* ── Left: Unit list ─────────────────────────────────────────────── */}
          <div className="lg:col-span-1 glass rounded-2xl border border-white/5 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-300">Einheiten</span>
              <span className="text-xs text-slate-500">{selectedCourse.units.length} gesamt</span>
            </div>

            <div className="flex-1 overflow-y-auto">
              {selectedCourse.units.map((unit, idx) => (
                <button
                  key={unit.id}
                  onClick={() => selectUnit(unit.id)}
                  className={`w-full text-left px-4 py-3 border-b border-white/5 hover:bg-white/5 transition-colors flex items-start gap-3 ${
                    selectedUnitId === unit.id
                      ? 'bg-[var(--color-primary)]/10 border-l-2 border-l-[var(--color-primary)]'
                      : ''
                  }`}
                >
                  <span className={`flex-shrink-0 w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center mt-0.5 ${
                    selectedUnitId === unit.id
                      ? 'bg-[var(--color-primary)] text-slate-900'
                      : 'bg-slate-700 text-slate-400'
                  }`}>
                    {idx + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate leading-tight">{unit.title}</p>
                    <p className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                      <Clock className="w-3 h-3" />
                      {unit.estimatedDuration} min
                      <span className="mx-1">·</span>
                      <HelpCircle className="w-3 h-3" />
                      {unit.contentBlocks
                        ? unit.contentBlocks.filter(b => b.type === 'quiz').reduce((s, b) => s + (b.questions?.length ?? 0), 0)
                        : unit.questions.length} Fragen
                      <span className="mx-1">·</span>
                      {unit.contentBlocks && unit.contentBlocks.length > 0 ? (
                        <span className="text-[var(--color-success)]">generiert</span>
                      ) : (
                        <span>Plan</span>
                      )}
                    </p>
                  </div>
                </button>
              ))}
            </div>

            <div className="p-3 border-t border-white/5">
              <button
                onClick={addUnit}
                disabled={saving}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 transition-colors border border-[var(--color-primary)]/30 disabled:opacity-50"
              >
                <Plus className="w-4 h-4" /> Neue Einheit
              </button>
            </div>
          </div>

          {/* ── Right: Unit detail ───────────────────────────────────────────── */}
          <div className="lg:col-span-3 flex flex-col gap-5">
            {!selectedUnit ? (
              <div className="glass rounded-2xl p-8 text-center border border-white/5">
                <p className="text-slate-500">Wähle links eine Einheit aus.</p>
              </div>
            ) : (
              <>
                {/* ── Unit info card ─────────────────────────────────────── */}
                <div className="glass rounded-2xl p-5 border border-white/5">

                  {/* Title row + action buttons */}
                  <div className="flex items-start justify-between gap-4 mb-4">
                    {isEditingUnit ? (
                      <input
                        type="text"
                        value={editingUnit?.title ?? ''}
                        onChange={e =>
                          setEditingUnit(prev => prev ? { ...prev, title: e.target.value } : prev)
                        }
                        className="flex-1 bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-lg font-semibold focus:outline-none focus:border-[var(--color-primary)]"
                      />
                    ) : (
                      <h3 className="text-lg font-semibold text-slate-100 leading-tight">{selectedUnit.title}</h3>
                    )}

                    <div className="flex items-center gap-2 flex-shrink-0">
                      {isEditingUnit ? (
                        <>
                          <button
                            onClick={cancelEditUnit}
                            className="px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 flex items-center gap-1 transition-colors"
                          >
                            <X className="w-4 h-4" /> Abbrechen
                          </button>
                          <button
                            onClick={saveUnit}
                            disabled={saving}
                            className="bg-[var(--color-success)]/20 hover:bg-[var(--color-success)]/30 text-[var(--color-success)] border border-[var(--color-success)]/30 px-3 py-1.5 rounded-lg text-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
                          >
                            <Save className="w-4 h-4" />
                            {saving ? 'Speichert…' : 'Speichern'}
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => generateUnit(selectedUnit.id)}
                            disabled={!!generatingUnitId || generatingAll}
                            className="bg-[var(--color-primary)]/20 hover:bg-[var(--color-primary)]/30 text-[var(--color-primary)] border border-[var(--color-primary)]/30 px-3 py-1.5 rounded-lg text-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
                          >
                            <RefreshCw className={`w-4 h-4 ${generatingUnitId === selectedUnit.id ? 'animate-spin' : ''}`} />
                            {selectedUnit.contentBlocks && selectedUnit.contentBlocks.length > 0 ? 'Neu generieren' : 'Einheit generieren'}
                          </button>
                          <button
                            onClick={startEditUnit}
                            className="glass px-3 py-1.5 rounded-lg text-sm text-slate-300 hover:text-white flex items-center gap-1.5 transition-colors"
                          >
                            <Edit2 className="w-4 h-4" /> Bearbeiten
                          </button>
                          <button
                            onClick={() => deleteUnit(selectedUnit.id)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 transition-colors"
                            title="Einheit löschen"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Duration */}
                  <div className="flex items-center gap-2 mb-4">
                    <Clock className="w-4 h-4 text-slate-500 flex-shrink-0" />
                    {isEditingUnit ? (
                      <>
                        <input
                          type="number"
                          min="1"
                          value={editingUnit?.estimatedDuration ?? 60}
                          onChange={e =>
                            setEditingUnit(prev =>
                              prev ? { ...prev, estimatedDuration: parseInt(e.target.value) || 60 } : prev
                            )
                          }
                          className="w-20 bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[var(--color-primary)]"
                        />
                        <span className="text-sm text-slate-400">Minuten</span>
                      </>
                    ) : (
                      <span className="text-sm text-slate-400">{selectedUnit.estimatedDuration} Minuten</span>
                    )}
                  </div>

                  {/* Description */}
                  <Section label="Beschreibung">
                    {isEditingUnit ? (
                      <textarea
                        rows={2}
                        value={editingUnit?.description ?? ''}
                        onChange={e =>
                          setEditingUnit(prev => prev ? { ...prev, description: e.target.value } : prev)
                        }
                        className={inputCls + ' resize-none'}
                        placeholder="Kurzbeschreibung der Einheit..."
                      />
                    ) : (
                      <p className="text-sm text-slate-300">
                        {selectedUnit.description || <Em>Keine Beschreibung</Em>}
                      </p>
                    )}
                  </Section>

                  {/* Learning objectives */}
                  <Section label="Lernziele" icon={<Target className="w-3 h-3" />}>
                    {isEditingUnit ? (
                      <div className="space-y-2">
                        {editingUnit?.learningObjectives.map((obj, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <input
                              type="text"
                              value={obj}
                              onChange={e => {
                                const updated = [...(editingUnit?.learningObjectives ?? [])];
                                updated[idx] = e.target.value;
                                setEditingUnit(prev =>
                                  prev ? { ...prev, learningObjectives: updated } : prev
                                );
                              }}
                              className={inputCls}
                            />
                            <button
                              onClick={() => {
                                const updated =
                                  editingUnit?.learningObjectives.filter((_, i) => i !== idx) ?? [];
                                setEditingUnit(prev =>
                                  prev ? { ...prev, learningObjectives: updated } : prev
                                );
                              }}
                              className="text-slate-500 hover:text-[var(--color-error)] transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={newObjective}
                            onChange={e => setNewObjective(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === 'Enter' && newObjective.trim()) {
                                setEditingUnit(prev =>
                                  prev
                                    ? { ...prev, learningObjectives: [...prev.learningObjectives, newObjective.trim()] }
                                    : prev
                                );
                                setNewObjective('');
                              }
                            }}
                            className={inputCls}
                            placeholder="Neues Lernziel (Enter zum Hinzufügen)"
                          />
                          <button
                            onClick={() => {
                              if (newObjective.trim()) {
                                setEditingUnit(prev =>
                                  prev
                                    ? { ...prev, learningObjectives: [...prev.learningObjectives, newObjective.trim()] }
                                    : prev
                                );
                                setNewObjective('');
                              }
                            }}
                            className="px-3 py-2 rounded-lg text-sm bg-slate-700 hover:bg-slate-600 transition-colors"
                          >
                            <Plus className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <ul className="space-y-1">
                        {selectedUnit.learningObjectives.length === 0 ? (
                          <li><Em>Keine Lernziele definiert</Em></li>
                        ) : (
                          selectedUnit.learningObjectives.map((obj, idx) => (
                            <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                              <ChevronRight className="w-4 h-4 text-[var(--color-primary)] flex-shrink-0 mt-0.5" />
                              {obj}
                            </li>
                          ))
                        )}
                      </ul>
                    )}
                  </Section>

                  {/* Theory content — only shown for units without contentBlocks */}
                  {!(selectedUnit.contentBlocks && selectedUnit.contentBlocks.length > 0) && (
                    <Section label="Theorieinhalt" icon={<BookOpen className="w-3 h-3" />} last>
                      {isEditingUnit ? (
                        <textarea
                          rows={8}
                          value={editingUnit?.theoryContent ?? ''}
                          onChange={e =>
                            setEditingUnit(prev => prev ? { ...prev, theoryContent: e.target.value } : prev)
                          }
                          className={inputCls + ' resize-y'}
                          placeholder="Lehrinhalt dieser Einheit..."
                        />
                      ) : (
                        <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                          {selectedUnit.theoryContent || <Em>Kein Theorieinhalt</Em>}
                        </p>
                      )}
                    </Section>
                  )}
                </div>

                {/* ── ContentBlocks card ─────────────────────────────────── */}
                {selectedUnit.contentBlocks && selectedUnit.contentBlocks.length > 0 && (
                  <ContentBlocksPanel
                    unit={selectedUnit}
                    editingUnit={editingUnit}
                    isEditing={isEditingUnit}
                    onEditBlock={(blockId, field, value) =>
                      setEditingUnit(prev => {
                        if (!prev) return prev;
                        const updatedBlocks = (prev.contentBlocks ?? []).map(b =>
                          b.id === blockId ? { ...b, [field]: value } : b
                        );
                        return { ...prev, contentBlocks: updatedBlocks };
                      })
                    }
                    onAddQuestion={openAddQuestion}
                    onEditQuestion={(q, blockId) => openEditQuestion(q, blockId)}
                    onDeleteQuestion={deleteQuestion}
                    saving={saving}
                  />
                )}

                {/* ── Questions card (flat list – shown when no contentBlocks) */}
                {!(selectedUnit.contentBlocks && selectedUnit.contentBlocks.length > 0) && (
                  <div className="glass rounded-2xl border border-white/5 overflow-hidden">
                    <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <HelpCircle className="w-5 h-5 text-[var(--color-primary)]" />
                        <h4 className="font-semibold">Fragen</h4>
                        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                          {selectedUnit.questions.length}
                        </span>
                      </div>
                      <button
                        onClick={() => openAddQuestion()}
                        className="flex items-center gap-2 bg-[var(--color-primary)]/20 hover:bg-[var(--color-primary)]/30 text-[var(--color-primary)] border border-[var(--color-primary)]/30 px-3 py-1.5 rounded-lg text-sm transition-colors"
                      >
                        <Plus className="w-4 h-4" /> Frage hinzufügen
                      </button>
                    </div>

                    {selectedUnit.questions.length === 0 ? (
                      <div className="p-10 text-center">
                        <HelpCircle className="w-8 h-8 mx-auto mb-2 text-slate-700" />
                        <p className="text-slate-500 text-sm">Noch keine Fragen. Füge eine neue Frage hinzu.</p>
                      </div>
                    ) : (
                      <div className="divide-y divide-white/5">
                        {selectedUnit.questions.map((q, idx) => (
                          <QuestionCard
                            key={q.id}
                            question={q}
                            index={idx + 1}
                            onEdit={() => openEditQuestion(q)}
                            onDelete={() => deleteQuestion(q.id)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Question editor modal ─────────────────────────────────────────────── */}
      {qEditorState && (
        <QuestionEditor
          question={qEditorState.question}
          onSave={handleQuestionSave}
          onCancel={() => setQEditorState(null)}
        />
      )}
    </div>
  );
}

// ─── Small layout helpers ─────────────────────────────────────────────────────

function Section({
  label,
  icon,
  last = false,
  children,
}: {
  label: string;
  icon?: React.ReactNode;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={last ? '' : 'mb-4'}>
      <label className="flex items-center gap-1 text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
        {icon} {label}
      </label>
      {children}
    </div>
  );
}

function Em({ children }: { children: React.ReactNode }) {
  return <span className="text-slate-600 italic text-sm">{children}</span>;
}

// ─── QuestionCard sub-component ───────────────────────────────────────────────

interface QuestionCardProps {
  question: Question;
  index: number;
  onEdit: () => void;
  onDelete: () => void;
}

function QuestionCard({ question, index, onEdit, onDelete }: QuestionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isCodeRunner = question.questionType === 'coderunner';

  return (
    <div className={`px-5 py-4 ${isCodeRunner ? 'bg-orange-500/5' : ''}`}>
      {/* Collapsed row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-700 text-xs font-bold flex items-center justify-center text-slate-400 mt-0.5">
            {index}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${Q_COLORS[question.questionType]}`}>
                {isCodeRunner && <Code className="w-3 h-3 inline mr-1" />}
                {Q_LABELS[question.questionType]}
              </span>
              {isCodeRunner && question.programmingLanguage && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 border border-slate-600">
                  {question.programmingLanguage}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-200 font-medium">{question.question}</p>
            <p className="text-xs text-slate-500 mt-0.5">{questionSummary(question)}</p>
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => setExpanded(v => !v)}
            title={expanded ? 'Einklappen' : 'Details anzeigen'}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          <button
            onClick={onEdit}
            title="Bearbeiten"
            className="p-1.5 rounded-lg text-slate-500 hover:text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 transition-colors"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            title="Löschen"
            className="p-1.5 rounded-lg text-slate-500 hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="mt-3 ml-9 space-y-3">

          {/* MC / oumultiresponse answers */}
          {(question.questionType === 'multiple-choice' || question.questionType === 'oumultiresponse') &&
            question.answers && (
              <div className="space-y-1">
                {question.answers.map(a => (
                  <div
                    key={a.id}
                    className={`flex items-start gap-2 text-xs px-3 py-2 rounded-lg ${
                      a.isCorrect
                        ? 'bg-[var(--color-success)]/10 border border-[var(--color-success)]/20'
                        : 'bg-slate-800/50'
                    }`}
                  >
                    <span
                      className={`w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center border mt-0.5 ${
                        a.isCorrect
                          ? 'bg-[var(--color-success)]/30 border-[var(--color-success)]'
                          : 'border-slate-600'
                      }`}
                    >
                      {a.isCorrect && <Check className="w-2.5 h-2.5 text-[var(--color-success)]" />}
                    </span>
                    <div>
                      <span className={a.isCorrect ? 'text-[var(--color-success)]' : 'text-slate-300'}>
                        {a.text}
                      </span>
                      {a.explanation && (
                        <p className="text-slate-500 mt-0.5">{a.explanation}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

          {/* Matching pairs */}
          {question.questionType === 'matching' && question.matchingPairs && (
            <div className="space-y-1">
              {question.matchingPairs.map(p => (
                <div key={p.id} className="flex items-center gap-2 text-xs">
                  <span className="flex-1 bg-slate-800/50 rounded px-2 py-1 text-slate-300">{p.left}</span>
                  <span className="text-slate-500">→</span>
                  <span className="flex-1 bg-slate-800/50 rounded px-2 py-1 text-slate-300">{p.right}</span>
                </div>
              ))}
            </div>
          )}

          {/* CodeRunner details */}
          {question.questionType === 'coderunner' && (
            <div className="space-y-2">
              {question.starterCode && (
                <div>
                  <p className="text-xs text-slate-500 mb-1 font-medium">Starter-Code:</p>
                  <pre className="text-xs bg-slate-900/80 rounded-lg p-3 text-slate-300 overflow-x-auto border border-slate-700/50">
                    {question.starterCode}
                  </pre>
                </div>
              )}
              {question.testCases && question.testCases.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 mb-1 font-medium">Testfälle:</p>
                  <div className="space-y-1">
                    {question.testCases.map(tc => (
                      <div key={tc.id} className="text-xs bg-slate-800/50 rounded px-3 py-2 font-mono">
                        <span className="text-slate-400">Input: </span>
                        <span className="text-slate-200">{tc.input}</span>
                        <span className="mx-2 text-slate-600">→</span>
                        <span className="text-[var(--color-success)]">{tc.expectedOutput}</span>
                        {tc.description && (
                          <span className="ml-2 text-slate-500 font-sans">({tc.description})</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Explanation */}
          {question.explanation && (
            <div className="text-xs bg-slate-800/30 rounded-lg px-3 py-2 text-slate-400 border border-slate-700/50">
              <span className="font-medium text-slate-500">Erklärung: </span>
              {question.explanation}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── ContentBlocksPanel sub-component ───────────────────────────────────────────────

const BLOCK_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  theory:     { label: 'Theorie',      icon: <BookOpen className="w-4 h-4" />,      color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  example:    { label: 'Beispiel',     icon: <Lightbulb className="w-4 h-4" />,     color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
  activity:   { label: 'Aktivität',   icon: <ClipboardList className="w-4 h-4" />, color: 'text-green-400 bg-green-500/10 border-green-500/20' },
  quiz:       { label: 'Quiz',         icon: <HelpCircle className="w-4 h-4" />,    color: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
  reflection: { label: 'Reflexion',    icon: <MessageSquare className="w-4 h-4" />, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20' },
  homework:   { label: 'Hausübung',   icon: <Home className="w-4 h-4" />,          color: 'text-slate-400 bg-slate-500/10 border-slate-500/20' },
};

interface ContentBlocksPanelProps {
  unit: TeachingUnit;
  editingUnit: TeachingUnit | null;
  isEditing: boolean;
  onEditBlock: (blockId: string, field: string, value: string) => void;
  onAddQuestion: (blockId: string) => void;
  onEditQuestion: (q: Question, blockId: string) => void;
  onDeleteQuestion: (questionId: string) => void;
  saving: boolean;
}

function isSelfStudyBlock(block: { type: string; title: string }) {
  const title = (block.title ?? '').toLowerCase();
  return block.type === 'homework'
    || block.type === 'reflection'
    || block.type === 'quiz'
    || title.startsWith('self study')
    || title.includes('selbststudium');
}

function unitIndex(unit: TeachingUnit) {
  const match = String(unit.id ?? '').match(/\d+/);
  return match ? Number(match[0]) : 1;
}

function selfStudyLetter(index: number) {
  return String.fromCharCode(64 + Math.max(1, Math.min(26, index)));
}

function stripSectionPrefix(title: string) {
  return (title || '')
    .replace(/^(Class|Praesenz|Präsenz)\s*\d+\s*:\s*/i, '')
    .replace(/^(Self[- ]?Study|Eigenstudium)\s*[A-Z]?\d*\s*:\s*/i, '')
    .trim();
}

function ContentBlocksPanel({
  unit, editingUnit, isEditing, onEditBlock, onAddQuestion, onEditQuestion, onDeleteQuestion, saving,
}: ContentBlocksPanelProps) {
  const blocks = (isEditing ? editingUnit?.contentBlocks : unit.contentBlocks) ?? [];
  const classBlocks = blocks.filter(block => !isSelfStudyBlock(block));
  const selfStudyBlocks = blocks.filter(block => isSelfStudyBlock(block));
  const idx = unitIndex(unit);

  const renderBlock = (block: typeof blocks[number], blockIdx: number) => {
    const meta = BLOCK_META[block.type] ?? BLOCK_META.activity;
    const isQuiz = block.type === 'quiz';
    const questions = isQuiz ? block.questions ?? [] : [];

    return (
      <div key={block.id} className="glass rounded-2xl border border-white/5 overflow-hidden">
        {/* Block header */}
        <div className="px-5 py-3 flex items-center justify-between border-b border-white/5">
          <div className="flex items-center gap-2">
            <span className={`flex items-center justify-center w-7 h-7 rounded-lg border ${meta.color}`}>
              {meta.icon}
            </span>
            {isEditing ? (
              <input
                type="text"
                value={stripSectionPrefix(block.title)}
                onChange={e => onEditBlock(block.id, 'title', e.target.value)}
                className="bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-1.5 text-sm font-medium focus:outline-none focus:border-[var(--color-primary)] w-64"
              />
            ) : (
              <h4 className="font-semibold text-sm">{stripSectionPrefix(block.title)}</h4>
            )}
            <span className={`text-xs px-2 py-0.5 rounded-full border ${meta.color}`}>{meta.label}</span>
            <span className="text-xs text-slate-500">Block {blockIdx + 1}</span>
          </div>
          {isQuiz && (
            <button
              onClick={() => onAddQuestion(block.id)}
              disabled={saving}
              className="flex items-center gap-1.5 bg-[var(--color-primary)]/20 hover:bg-[var(--color-primary)]/30 text-[var(--color-primary)] border border-[var(--color-primary)]/30 px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
            >
              <Plus className="w-3 h-3" /> Frage
            </button>
          )}
        </div>

        {/* Block body */}
        {!isQuiz && (
          <div className="px-5 py-4">
            {isEditing ? (
              <textarea
                rows={5}
                value={block.content ?? ''}
                onChange={e => onEditBlock(block.id, 'content', e.target.value)}
                className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-primary)] resize-y"
                placeholder={`Inhalt fuer ${meta.label}...`}
              />
            ) : (
              <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                {block.content || <span className="italic text-slate-600">Kein Inhalt</span>}
              </p>
            )}
          </div>
        )}

        {/* Quiz block questions */}
        {isQuiz && (
          <div>
            {questions.length === 0 ? (
              <div className="p-8 text-center">
                <HelpCircle className="w-8 h-8 mx-auto mb-2 text-slate-700" />
                <p className="text-slate-500 text-sm">Keine Fragen. Klicke Frage um eine hinzuzufuegen.</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {questions.map((q, idx) => (
                  <QuestionCard
                    key={q.id}
                    question={q}
                    index={idx + 1}
                    onEdit={() => onEditQuestion(q, block.id)}
                    onDelete={() => onDeleteQuestion(q.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderGroup = (title: string, subtitle: string, groupedBlocks: typeof blocks) => (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between px-1">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className="text-xs text-slate-500">{groupedBlocks.length} Bloecke</span>
      </div>
      {groupedBlocks.length === 0 ? (
        <div className="glass rounded-2xl border border-white/5 p-5 text-sm text-slate-500">
          Noch keine Inhalte in diesem Bereich.
        </div>
      ) : (
        groupedBlocks.map((block, idx) => renderBlock(block, idx))
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-6">
      {renderGroup(`Class ${idx}: ${unit.title}`, 'Praesenzphase mit Theorie, Beispielen und gemeinsamer Aktivitaet', classBlocks)}
      {renderGroup(`Self-Study ${selfStudyLetter(idx)}: ${unit.title}`, 'Selbststudium mit Vertiefung, Aufgabe und Lerncheck', selfStudyBlocks)}
    </div>
  );
}
