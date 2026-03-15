import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import {
    Activity, ArrowRight, BookOpen, AlertCircle, TrendingUp, Filter, Eye, RefreshCw,
    Layers, ChevronDown, ChevronUp, FileText, Building2
} from 'lucide-react';

/* ───────── Types ───────── */

interface HeatmapItem { field_name: string; cnt: number; }
interface BankRankItem { institution_name: string; change_count: number; }

interface OverrideSummary {
    total_overrides: number;
    total_documents: number;
    top_problem_field: string;
    top_problem_count: number;
    field_heatmap: HeatmapItem[];
    bank_ranking: BankRankItem[];
}

interface TransactionRow { [key: string]: any; }

interface OverrideItem {
    override_id: number;
    field_name: string;
    ai_value: string;
    user_value: string;
    overridden_at: string;
    original_transaction: TransactionRow | null;
    corrected_transaction: TransactionRow | null;
}

interface DocumentOverrides {
    document_id: number;
    file_name: string;
    institution_name: string;
    total_changes: number;
    overrides: OverrideItem[];
}

/* ───────── Helper: colour intensity for heat map ───────── */
function heatColor(value: number, max: number): string {
    if (max === 0) return '#f1f5f9';
    const ratio = value / max;
    // gradient from cool blue to hot red
    if (ratio < 0.25) return '#dbeafe'; // light blue
    if (ratio < 0.5) return '#fef08a';  // yellow
    if (ratio < 0.75) return '#fdba74'; // orange
    return '#fca5a5';                    // red
}
function heatTextColor(value: number, max: number): string {
    if (max === 0) return '#334155';
    const ratio = value / max;
    if (ratio < 0.5) return '#1e293b';
    return '#7f1d1d';
}

/* ───────── Component ───────── */

export default function FrequentTransactions() {
    const [summary, setSummary] = useState<OverrideSummary | null>(null);
    const [documentData, setDocumentData] = useState<DocumentOverrides[]>([]);
    const [loading, setLoading] = useState(true);

    // UI states
    const [expandedDocId, setExpandedDocId] = useState<number | null>(null);
    const [selectedOverrideId, setSelectedOverrideId] = useState<number | null>(null);
    const [searchQuery, setSearchQuery] = useState('');

    // LLM Report State
    const [generatingReport, setGeneratingReport] = useState(false);
    const [reportText, setReportText] = useState<string | null>(null);

    /* ── Fetch ── */
    const fetchData = async () => {
        setLoading(true);
        try {
            const [summaryRes, overridesRes] = await Promise.all([
                axios.get('http://localhost:8000/api/frequent-overrides-summary'),
                axios.get('http://localhost:8000/api/frequent-overrides')
            ]);
            setSummary(summaryRes.data);
            setDocumentData(overridesRes.data);
            if (overridesRes.data?.length > 0) setExpandedDocId(overridesRes.data[0].document_id);
        } catch (error) { console.error('Error fetching frequent overrides:', error); }
        finally { setLoading(false); }
    };
    useEffect(() => { fetchData(); }, []);

    const handleGenerateReport = async () => {
        setGeneratingReport(true); setReportText(null);
        try {
            const res = await axios.post('http://localhost:8000/api/generate-llm-report');
            setReportText(res.data.report_text);
        } catch (error) {
            console.error(error);
            setReportText("Failed to generate report.");
        } finally { setGeneratingReport(false); }
    };

    const toggleDoc = (id: number) => {
        setExpandedDocId(prev => prev === id ? null : id);
        setSelectedOverrideId(null);
    };
    const toggleOverrideContext = (id: number) => setSelectedOverrideId(prev => prev === id ? null : id);

    // Filter
    const filteredDocs = useMemo(() =>
        documentData.filter(d => d.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                                  d.institution_name.toLowerCase().includes(searchQuery.toLowerCase())),
        [documentData, searchQuery]
    );

    // Heat map max
    const heatMax = useMemo(() => Math.max(...(summary?.field_heatmap?.map(h => h.cnt) || [0])), [summary]);

    /* ────────────────── RENDER ────────────────── */
    return (
        <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '1400px' }}>

            {/* ══════════ HEADER ══════════ */}
            <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.5rem 2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div className="icon-wrapper" style={{ marginBottom: 0, width: '50px', height: '50px', background: 'linear-gradient(135deg, #fef3c7, #fef08a)', color: '#d97706' }}>
                        <Activity size={24} />
                    </div>
                    <div>
                        <h1 className="page-title" style={{ fontSize: '1.8rem', margin: 0 }}>Frequent AI Errors</h1>
                        <p className="page-subtitle" style={{ fontSize: '0.9rem', margin: 0 }}>Track user corrections &bull; Heat map &bull; Bank ranking &bull; Before / After view</p>
                    </div>
                </div>
                <button onClick={handleGenerateReport} disabled={generatingReport}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1.5rem', borderRadius: '8px', fontWeight: 600, color: '#fff', border: 'none', cursor: generatingReport ? 'not-allowed' : 'pointer', background: generatingReport ? 'rgba(139,92,246,.5)' : '#8b5cf6', boxShadow: generatingReport ? 'none' : '0 4px 12px rgba(139,92,246,.3)', transition: 'all .2s' }}>
                    {generatingReport ? <RefreshCw className="animate-spin" size={18} /> : <BookOpen size={18} fill="currentColor" />}
                    <span>{generatingReport ? 'Analyzing…' : 'Generate LLM Prompt Report'}</span>
                </button>
            </div>

            {/* ══════════ LLM REPORT ══════════ */}
            {reportText && (
                <div className="glass-card" style={{ padding: '2rem', borderLeft: '4px solid #8b5cf6', background: '#f5f3ff' }}>
                    <h3 style={{ marginTop: 0, color: '#4c1d95', display: 'flex', alignItems: 'center', gap: 8 }}><BookOpen size={20} /> AI Extraction Improvement Strategy</h3>
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem', color: '#4c1d95', lineHeight: 1.6, background: '#ede9fe', padding: '1rem', borderRadius: '8px', border: '1px solid #ddd6fe' }}>{reportText}</div>
                    <button onClick={() => setReportText(null)} style={{ marginTop: '1rem', padding: '0.5rem 1rem', background: 'transparent', border: '1px solid #8b5cf6', color: '#8b5cf6', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>Dismiss Report</button>
                </div>
            )}

            {/* ══════════ SUMMARY CARDS ══════════ */}
            {summary && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    <SummaryCard icon={<AlertCircle size={24} color="#f59e0b" />} label="Total Corrections" value={summary.total_overrides} accent="#f59e0b" />
                    <SummaryCard icon={<Layers size={24} color="#3b82f6" />} label="Documents Affected" value={summary.total_documents} />
                    <SummaryCard icon={<TrendingUp size={24} color="#ef4444" />} label="Top Problem Field" value={`${summary.top_problem_field} (${summary.top_problem_count})`} accent="#ef4444" valueColor="#ef4444" />
                </div>
            )}

            {/* ══════════ HEAT MAP + BANK RANKING (side-by-side) ══════════ */}
            {summary && (summary.field_heatmap.length > 0 || summary.bank_ranking.length > 0) && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>

                    {/* HEAT MAP */}
                    <div className="glass-card" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', color: '#1e293b', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: '1.2rem' }}>🔥</span> Field Change Heat Map
                        </h3>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.75rem' }}>
                            {summary.field_heatmap.map(h => (
                                <div key={h.field_name} style={{
                                    padding: '1rem', borderRadius: '10px', textAlign: 'center',
                                    background: heatColor(h.cnt, heatMax),
                                    border: `1px solid ${heatColor(h.cnt, heatMax)}`,
                                    transition: 'transform .15s',
                                    cursor: 'default'
                                }}
                                    onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.05)')}
                                    onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
                                >
                                    <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700, color: heatTextColor(h.cnt, heatMax), letterSpacing: '0.04em' }}>{h.field_name}</div>
                                    <div style={{ fontSize: '1.6rem', fontWeight: 800, color: heatTextColor(h.cnt, heatMax), marginTop: '0.25rem' }}>{h.cnt}</div>
                                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>corrections</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* BANK RANKING */}
                    <div className="glass-card" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', color: '#1e293b', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Building2 size={18} color="#6366f1" /> Bank Statement Error Ranking
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {summary.bank_ranking.map((b, i) => {
                                const maxBank = summary.bank_ranking[0]?.change_count || 1;
                                const pct = Math.round((b.change_count / maxBank) * 100);
                                return (
                                    <div key={b.institution_name} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                        <span style={{ width: '22px', textAlign: 'center', fontSize: '0.8rem', fontWeight: 700, color: i === 0 ? '#ef4444' : '#64748b' }}>
                                            {i + 1}
                                        </span>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                                                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1e293b' }}>{b.institution_name || 'Unknown'}</span>
                                                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: i === 0 ? '#ef4444' : '#475569' }}>{b.change_count}</span>
                                            </div>
                                            <div style={{ height: '6px', borderRadius: '3px', background: '#f1f5f9', overflow: 'hidden' }}>
                                                <div style={{ height: '100%', width: `${pct}%`, borderRadius: '3px', background: i === 0 ? '#ef4444' : '#6366f1', transition: 'width .5s ease' }} />
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                            {summary.bank_ranking.length === 0 && <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>No bank data yet</div>}
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════ SEARCH ══════════ */}
            <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.5rem', borderRadius: '12px' }}>
                <Filter size={20} color="#64748b" />
                <span style={{ color: '#475569', fontWeight: 600, fontSize: '0.9rem' }}>Search:</span>
                <input type="text" placeholder="Search by Document Name or Bank…" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                    style={{ padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border-color)', background: '#fff', color: '#1e293b', fontSize: '0.85rem', width: '350px', outline: 'none' }} />
            </div>

            {/* ══════════ DOCUMENT LIST ══════════ */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {loading && <div className="glass-card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>Loading corrections data…</div>}
                {!loading && filteredDocs.length === 0 && <div className="glass-card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>No documents with corrections found 🎉</div>}

                {!loading && filteredDocs.map((doc, index) => (
                    <div key={doc.document_id} className="glass-card" style={{ overflow: 'hidden', padding: 0 }}>

                        {/* ── Document Header ── */}
                        <div onClick={() => toggleDoc(doc.document_id)}
                            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.25rem 1.5rem', cursor: 'pointer', background: expandedDocId === doc.document_id ? '#f8fafc' : '#fff', borderBottom: expandedDocId === doc.document_id ? '1px solid #e2e8f0' : 'none', transition: 'background .2s' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 40, borderRadius: '50%', background: index === 0 ? '#fee2e2' : '#f1f5f9', color: index === 0 ? '#ef4444' : '#64748b' }}>
                                    <FileText size={20} />
                                </div>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        {doc.file_name}
                                        {index === 0 && <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem', background: '#ef4444', color: '#fff', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 700 }}>Highest Priority</span>}
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Building2 size={13} /> {doc.institution_name}
                                        <span style={{ opacity: 0.4 }}>•</span>
                                        Doc ID: {doc.document_id}
                                    </div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
                                <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#ef4444', lineHeight: 1 }}>{doc.total_changes}</div>
                                    <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Corrections</div>
                                </div>
                                <div style={{ color: '#94a3b8' }}>{expandedDocId === doc.document_id ? <ChevronUp size={24} /> : <ChevronDown size={24} />}</div>
                            </div>
                        </div>

                        {/* ── Expanded Override Table ── */}
                        {expandedDocId === doc.document_id && (
                            <div style={{ padding: '1.5rem', background: '#f8fafc' }}>
                                <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                        <thead style={{ background: '#f1f5f9', borderBottom: '1px solid #cbd5e1' }}>
                                            <tr>
                                                <th style={thStyle}>Date Edited</th>
                                                <th style={thStyle}>Field Fixed</th>
                                                <th style={thStyle}>Original AI Output</th>
                                                <th style={thStyle}>User Correction</th>
                                                <th style={{ ...thStyle, textAlign: 'right' }}>Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {doc.overrides.map((ov, i) => (
                                                <React.Fragment key={ov.override_id}>
                                                    <tr style={{ borderBottom: i === doc.overrides.length - 1 && selectedOverrideId !== ov.override_id ? 'none' : '1px solid #f1f5f9' }}>
                                                        <td style={tdStyle}>{ov.overridden_at ? new Date(ov.overridden_at).toLocaleString() : 'N/A'}</td>
                                                        <td style={tdStyle}><FieldBadge name={ov.field_name} /></td>
                                                        <td style={tdStyle}><span style={{ color: '#ef4444', textDecoration: 'line-through', fontSize: '.9rem' }}>{ov.ai_value || '(empty)'}</span></td>
                                                        <td style={tdStyle}><span style={{ color: '#10b981', fontWeight: 600, fontSize: '.9rem' }}>{ov.user_value || '(empty)'}</span></td>
                                                        <td style={{ ...tdStyle, textAlign: 'right' }}>
                                                            <button onClick={() => toggleOverrideContext(ov.override_id)}
                                                                style={{ padding: '.4rem .8rem', background: selectedOverrideId === ov.override_id ? '#6366f1' : '#f8fafc', color: selectedOverrideId === ov.override_id ? '#fff' : '#475569', border: `1px solid ${selectedOverrideId === ov.override_id ? '#6366f1' : '#cbd5e1'}`, borderRadius: '6px', fontSize: '.8rem', fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '.3rem', transition: 'all .15s' }}>
                                                                <Eye size={14} />{selectedOverrideId === ov.override_id ? 'Hide' : 'Compare'}
                                                            </button>
                                                        </td>
                                                    </tr>

                                                    {/* ── Before / After comparison ── */}
                                                    {selectedOverrideId === ov.override_id && (
                                                        <tr><td colSpan={5} style={{ padding: 0, background: '#f1f5f9', borderBottom: '2px solid #6366f1' }}>
                                                            <div style={{ padding: '1.5rem' }}>
                                                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                                                    {/* BEFORE */}
                                                                    <div style={{ background: '#fff', borderRadius: '10px', border: '2px solid #fca5a5', padding: '1.25rem', position: 'relative' }}>
                                                                        <div style={{ position: 'absolute', top: '-10px', left: '12px', background: '#ef4444', color: '#fff', fontSize: '.65rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>Before (AI Output)</div>
                                                                        {ov.original_transaction ? (
                                                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '.75rem', marginTop: '.5rem' }}>
                                                                                {Object.entries(ov.original_transaction).map(([k, v]) => {
                                                                                    const changed = k === ov.field_name;
                                                                                    return (
                                                                                        <div key={k} style={{ padding: '.4rem', borderRadius: '6px', background: changed ? '#fee2e2' : '#f8fafc', border: changed ? '1px solid #fca5a5' : '1px solid transparent' }}>
                                                                                            <div style={{ fontSize: '.65rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>{k}</div>
                                                                                            <div style={{ fontSize: '.85rem', color: changed ? '#ef4444' : '#0f172a', fontWeight: changed ? 700 : 500, wordBreak: 'break-word' }}>
                                                                                                {v !== null && v !== undefined ? String(v) : '-'}
                                                                                            </div>
                                                                                        </div>
                                                                                    );
                                                                                })}
                                                                            </div>
                                                                        ) : <div style={{ color: '#94a3b8', fontSize: '.85rem' }}>Original not found</div>}
                                                                    </div>

                                                                    {/* AFTER */}
                                                                    <div style={{ background: '#fff', borderRadius: '10px', border: '2px solid #86efac', padding: '1.25rem', position: 'relative' }}>
                                                                        <div style={{ position: 'absolute', top: '-10px', left: '12px', background: '#10b981', color: '#fff', fontSize: '.65rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>After (User Corrected)</div>
                                                                        {ov.corrected_transaction ? (
                                                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '.75rem', marginTop: '.5rem' }}>
                                                                                {Object.entries(ov.corrected_transaction).map(([k, v]) => {
                                                                                    const changed = k === ov.field_name;
                                                                                    return (
                                                                                        <div key={k} style={{ padding: '.4rem', borderRadius: '6px', background: changed ? '#dcfce7' : '#f8fafc', border: changed ? '1px solid #86efac' : '1px solid transparent' }}>
                                                                                            <div style={{ fontSize: '.65rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>{k}</div>
                                                                                            <div style={{ fontSize: '.85rem', color: changed ? '#10b981' : '#0f172a', fontWeight: changed ? 700 : 500, wordBreak: 'break-word' }}>
                                                                                                {v !== null && v !== undefined ? String(v) : '-'}
                                                                                            </div>
                                                                                            {changed && (
                                                                                                <div style={{ marginTop: '.25rem', fontSize: '.7rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 700 }}>
                                                                                                    <ArrowRight size={10} /> corrected
                                                                                                </div>
                                                                                            )}
                                                                                        </div>
                                                                                    );
                                                                                })}
                                                                            </div>
                                                                        ) : <div style={{ color: '#94a3b8', fontSize: '.85rem' }}>Corrected version not available</div>}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </td></tr>
                                                    )}
                                                </React.Fragment>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

/* ═══════════ Small helpers ═══════════ */

const thStyle: React.CSSProperties = { padding: '0.75rem 1rem', fontSize: '0.8rem', color: '#475569', fontWeight: 600 };
const tdStyle: React.CSSProperties = { padding: '1rem', fontSize: '0.85rem', color: '#64748b', whiteSpace: 'nowrap' as const };

function FieldBadge({ name }: { name: string }) {
    return (
        <div style={{ display: 'inline-block', padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '.75rem', fontWeight: 700, background: '#fef3c7', color: '#d97706' }}>
            {name}
        </div>
    );
}

function SummaryCard({ icon, label, value, accent, valueColor }: { icon: React.ReactNode; label: string; value: string | number; accent?: string; valueColor?: string }) {
    return (
        <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px', borderBottom: accent ? `3px solid ${accent}` : 'none' }}>
            <div style={{ marginBottom: '0.5rem' }}>{icon}</div>
            <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
            <span style={{ fontSize: '1.4rem', fontWeight: 700, color: valueColor || '#1e293b', marginTop: '0.25rem' }}>{value}</span>
        </div>
    );
}
