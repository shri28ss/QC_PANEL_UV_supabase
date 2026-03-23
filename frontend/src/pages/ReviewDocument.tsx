import { useEffect, useState } from 'react';
import axios from 'axios';
import { FileCheck, Loader2, Code2, FileText, Cpu, Sparkles, Wand2, Play, CheckCircle2, AlertTriangle, Save, Check } from 'lucide-react';

interface ReviewDocumentData {
    statement_id: number;
    document_id: number;
    user_id: number;
    statement_type: string;
    institution_name: string;
    format_status: string;
    doc_status: string;
    transaction_parsed_type: string;
    is_auto_flagged: number;
    last_qc_accuracy: number | null;
}
interface Transaction {
    date: string;
    details: string;
    debit: number | null;
    credit: number | null;
    balance?: number | null;
}

interface FieldFlags {
    date_mismatch?: boolean;
    amount_mismatch?: boolean;
    detail_mismatch?: boolean;
}

interface MatchedPair {
    code: Transaction;
    llm: Transaction;
    score: number;
    desc_similarity: number;
}

interface DocumentLogicData {
    extraction_logic: string;
    code_transactions: string;
    llm_transactions: string;
    reconciliation: {
        matched_pairs: MatchedPair[];
        field_flags: FieldFlags[];
        unmatched_code: Transaction[];
        unmatched_llm: Transaction[];
        overall_similarity: number;
        summary: {
            total_code: number;
            total_llm: number;
            matched_count: number;
            unmatched_code_count: number;
            unmatched_llm_count: number;
        };
    };
}

export default function ReviewDocument() {
    const [documents, setDocuments] = useState<ReviewDocumentData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
    const [logicData, setLogicData] = useState<DocumentLogicData | null>(null);
    const [isFetchingLogic, setIsFetchingLogic] = useState(false);
    const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
    const [pdfError, setPdfError] = useState<string | null>(null);

    // Code improvement state
    const [originalCode, setOriginalCode] = useState<string>('');
    const [improvedCode, setImprovedCode] = useState<string>('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [isRunningLLM, setIsRunningLLM] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');
    const [isForceSaving, setIsForceSaving] = useState(false);
    const [forceSaveStatus, setForceSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');
    const [runResult, setRunResult] = useState<{ new_transactions: Transaction[], reconciliation: any, transaction_count: number, error?: string } | null>(null);


    useEffect(() => {
        const fetchDocuments = async () => {
            try {
                setLoading(true);
                const response = await axios.get('https://qc-panel-uv-supabase-1.onrender.com/api/review-documents');
                setDocuments(response.data);
                setError(null);
            } catch (err) {
                console.error('Error fetching documents:', err);
                setError('Failed to load documents. Please ensure the backend server is running.');
            } finally {
                setLoading(false);
            }
        };

        fetchDocuments();
    }, []);

    const handleRowClick = async (docId: number) => {
        if (selectedDocId === docId) return;

        setSelectedDocId(docId);
        setLogicData(null);
        setIsFetchingLogic(true);

        // Revoke old blob URL to free memory
        setPdfError(null);
        if (pdfBlobUrl) {
            URL.revokeObjectURL(pdfBlobUrl);
            setPdfBlobUrl(null);
        }

        try {
            // Fetch logic data and PDF blob in parallel
            const [logicRes, pdfRes] = await Promise.all([
                axios.get(`https://qc-panel-uv-supabase-1.onrender.com/api/document-logic/${docId}`),
                axios.get(`https://qc-panel-uv-supabase-1.onrender.com/api/document-pdf/${docId}`, {
                    responseType: 'blob',
                    validateStatus: (s) => s < 500, // don't throw on 404
                })
            ]);

            setLogicData(logicRes.data);

            if (pdfRes.status === 200) {
                // Create a blob URL for the PDF so the iframe can render it inline
                const blob = new Blob([pdfRes.data], { type: 'application/pdf' });
                const url = URL.createObjectURL(blob);
                setPdfBlobUrl(url);
            } else {
                // PDF not accessible — set error state (no blocking popup)
                const text = await (pdfRes.data as Blob).text();
                try {
                    const errData = JSON.parse(text);
                    console.warn('PDF not accessible:', errData.error);
                    setPdfError(errData.error || 'PDF file not found in storage.');
                } catch {
                    console.warn('PDF fetch failed with status', pdfRes.status);
                    setPdfError('PDF file could not be loaded (HTTP ' + pdfRes.status + ').');
                }
                setPdfBlobUrl(null);
            }
        } catch (err) {
            console.error('Error fetching data:', err);
        } finally {
            setIsFetchingLogic(false);
        }
    };

    const [remarks, setRemarks] = useState<Record<string, string>>({});
    const [trustAllMatchesAs, setTrustAllMatchesAs] = useState<'code' | 'llm' | null>(null);

    const handleTrustAllMatches = (source: 'code' | 'llm') => {
        setTrustAllMatchesAs(source);
        // We don't need to manually fill all remarks; the backend will interpret this flag
    };

    // Generate matched remarks duplication on the fly when preparing for backend
    const prepareRemarksForBackend = (baseRemarks: Record<string, string>) => {
        const enriched = { ...baseRemarks };

        if (trustAllMatchesAs) {
            enriched['global_trust_all_matches'] = trustAllMatchesAs === 'code' ? '[TRUST_CODE_FOR_ALL_MATCHES]' : '[TRUST_LLM_FOR_ALL_MATCHES]';
        }

        // Make sure any remark on matched_code_i is also on matched_llm_i, and vice versa
        Object.keys(enriched).forEach(key => {
            if (key.startsWith('matched_code_')) {
                const llmKey = key.replace('matched_code_', 'matched_llm_');
                if (!enriched[llmKey]) enriched[llmKey] = enriched[key];
            } else if (key.startsWith('matched_llm_')) {
                const codeKey = key.replace('matched_llm_', 'matched_code_');
                if (!enriched[codeKey]) enriched[codeKey] = enriched[key];
            }
        });

        return enriched;
    };
    const [manualFlags, setManualFlags] = useState<Record<string, FieldFlags>>({});
    const [acceptedTxns, setAcceptedTxns] = useState<Set<string>>(new Set());

    const toggleAccept = (id: string) => {
        setAcceptedTxns(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const handleRemarkChange = (id: string, value: string) => {
        setRemarks(prev => ({ ...prev, [id]: value }));
    };

    const toggleFlag = (id: string, flagKey: keyof FieldFlags) => {
        setManualFlags(prev => {
            const current = prev[id] || {};
            return { ...prev, [id]: { ...current, [flagKey]: !current[flagKey] } };
        });
    };

    const cellHighlight = (hasFlag: boolean) => ({
        backgroundColor: hasFlag ? 'rgba(248, 113, 113, 0.15)' : 'transparent',
        borderLeft: hasFlag ? '2px solid #ef4444' : '2px solid transparent',
    });

    // ============ CODE IMPROVEMENT HANDLERS ============

    const handleGenerateImprovedCode = async () => {
        if (!selectedDocId || !logicData) return;
        setIsGenerating(true);
        setImprovedCode('');
        setRunResult(null);
        setSaveStatus('idle');
        setForceSaveStatus('idle');
        try {
            // Build accepted info into remarks so the LLM understands them
            const enrichedRemarks = prepareRemarksForBackend(remarks);
            acceptedTxns.forEach(id => {
                if (!enrichedRemarks[id]) {
                    enrichedRemarks[id] = 'QC ACCEPTED: This transaction is correct, keep it as-is';
                } else {
                    enrichedRemarks[id] += ' | QC ACCEPTED: This transaction is correct';
                }
            });

            const response = await axios.post(`https://qc-panel-uv-supabase-1.onrender.com/api/improve-code/${selectedDocId}`, {
                reconciliation: logicData.reconciliation,
                remarks: enrichedRemarks,
                accepted_ids: Array.from(acceptedTxns),
            });

            // Check if the backend returned an error
            if (response.data.error) {
                alert(`Code generation failed: ${response.data.error}`);
                return;
            }

            // Keep the very first 'original' code stable so the diff remains meaningful
            if (!originalCode) {
                setOriginalCode(response.data.original_code || '');
            }
            setImprovedCode(response.data.improved_code || '');
        } catch (err: any) {
            console.error('Error generating improved code:', err);
            const message = err?.response?.data?.detail || err?.response?.data?.error || err?.message || 'Unknown error';
            alert(`Failed to generate improved code: ${message}`);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleRunImprovedCode = async () => {
        if (!selectedDocId || !improvedCode) return;
        setIsRunning(true);
        setRunResult(null);
        try {
            const response = await axios.post(`https://qc-panel-uv-supabase-1.onrender.com/api/run-improved-code/${selectedDocId}`, {
                improved_code: improvedCode,
            });
            setRunResult(response.data);

        } catch (err) {
            console.error('Error running improved code:', err);
            setRunResult({ error: 'Request failed', new_transactions: [], reconciliation: null, transaction_count: 0 });
        } finally {
            setIsRunning(false);
        }
    };

    const handleRunLLM = async () => {
        if (!selectedDocId) return;
        setIsRunningLLM(true);
        try {
            const response = await axios.post(`https://qc-panel-uv-supabase-1.onrender.com/api/run-llm/${selectedDocId}`);
            if (response.data.success) {
                setLogicData(prev => prev ? {
                    ...prev,
                    llm_transactions: JSON.stringify(response.data.llm_transactions),
                    reconciliation: response.data.reconciliation
                } : prev);
            } else if (response.data.error) {
                alert(response.data.error);
            }
        } catch (err) {
            console.error('Error running LLM:', err);
            alert('Failed to run LLM extraction.');
        } finally {
            setIsRunningLLM(false);
        }
    };

    const handleSaveImprovedCode = async (overwriteLlm: boolean = false) => {
        if (!selectedDocId || !improvedCode) return;
        setIsSaving(true);
        setSaveStatus('idle');
        try {
            await axios.post(`https://qc-panel-uv-supabase-1.onrender.com/api/save-improved-code/${selectedDocId}`, {
                improved_code: improvedCode,
                overwrite_llm: overwriteLlm,
                accuracy: overwriteLlm ? 100 : (runResult?.reconciliation?.overall_similarity || null),
            });
            setSaveStatus('saved');

            // Re-fetch the full document logic so all panels refresh with new transactions
            const logicRes = await axios.get(`https://qc-panel-uv-supabase-1.onrender.com/api/document-logic/${selectedDocId}`);
            setLogicData(logicRes.data);

            // Update the format_status, accuracy, and QC flag in the local documents list
            const savedAccuracy = overwriteLlm ? 100 : (runResult?.reconciliation?.overall_similarity || logicRes.data?.reconciliation?.overall_similarity || null);
            setDocuments(prev => prev.map(doc =>
                doc.document_id === selectedDocId
                    ? { ...doc, format_status: 'ACTIVE', last_qc_accuracy: savedAccuracy, is_auto_flagged: 0 }
                    : doc
            ));
        } catch (err) {
            console.error('Error saving improved code:', err);
            setSaveStatus('error');
        } finally {
            setIsSaving(false);
        }
    };

    const handleForceSaveImprovedCode = async () => {
        if (!selectedDocId || !improvedCode) return;
        if (!confirm('Are you sure you want to force save this code? The accuracy is below the 95% threshold.')) return;
        setIsForceSaving(true);
        setForceSaveStatus('idle');
        try {
            await axios.post(`https://qc-panel-uv-supabase-1.onrender.com/api/save-improved-code/${selectedDocId}`, {
                improved_code: improvedCode,
                overwrite_llm: false,
                accuracy: runResult?.reconciliation?.overall_similarity ?? null,
            });
            setForceSaveStatus('saved');
            setSaveStatus('saved'); // Also mark normal save as done to prevent double save

            // Re-fetch the full document logic so all panels refresh with new transactions
            const logicRes = await axios.get(`https://qc-panel-uv-supabase-1.onrender.com/api/document-logic/${selectedDocId}`);
            setLogicData(logicRes.data);

            // Update the format_status, accuracy, and QC flag in the local documents list
            const savedAccuracy = runResult?.reconciliation?.overall_similarity ?? logicRes.data?.reconciliation?.overall_similarity ?? null;
            setDocuments(prev => prev.map(doc =>
                doc.document_id === selectedDocId
                    ? { ...doc, format_status: 'ACTIVE', last_qc_accuracy: savedAccuracy, is_auto_flagged: 0 }
                    : doc
            ));
        } catch (err) {
            console.error('Error force saving improved code:', err);
            setForceSaveStatus('error');
        } finally {
            setIsForceSaving(false);
        }
    };




    const computeDiff = (original: string, improved: string) => {
        const origLines = original.split('\n');
        const impLines = improved.split('\n');

        // Simple LCS-based diff: mark each improved line as added/removed/unchanged
        // For performance, use a set-based approach with line fingerprinting
        const origTrimSet = new Set(origLines.map(l => l.trim()));

        type DiffLine = { type: 'added' | 'removed' | 'unchanged'; line: string; lineNo: number };
        const result: DiffLine[] = [];

        // Find lines in original that are gone
        const newTrimSet = new Set(impLines.map(l => l.trim()));
        const removedLines = origLines.filter(l => l.trim().length > 0 && !newTrimSet.has(l.trim()));

        let lineNo = 1;
        for (const line of impLines) {
            const trimmed = line.trim();
            const isNew = trimmed.length > 0 && !origTrimSet.has(trimmed);
            result.push({
                type: isNew ? 'added' : 'unchanged',
                line,
                lineNo: lineNo++,
            });
        }

        return { diffLines: result, removedCount: removedLines.length, addedCount: result.filter(l => l.type === 'added').length };
    };

    const renderDiffCode = (original: string, improved: string) => {
        const { diffLines, removedCount, addedCount } = computeDiff(original, improved);
        const unchangedCount = diffLines.length - addedCount;

        return (
            <>
                {/* Diff Legend */}
                <div style={{
                    display: 'flex', gap: '1rem', padding: '0.4rem 0.75rem',
                    borderBottom: '1px solid #e2e8f0', fontSize: '0.65rem',
                    background: '#f8fafc', alignItems: 'center', flexWrap: 'wrap',
                }}>
                    <span style={{ fontWeight: 700, color: '#475569' }}>DIFF</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#16a34a' }}>
                        <span style={{ background: '#dcfce7', border: '1px solid #86efac', borderRadius: '3px', padding: '0 4px', fontSize: '0.6rem', fontWeight: 700 }}>+{addedCount}</span>
                        lines added / modified
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#dc2626' }}>
                        <span style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: '3px', padding: '0 4px', fontSize: '0.6rem', fontWeight: 700 }}>−{removedCount}</span>
                        lines removed
                    </span>
                    <span style={{ color: '#94a3b8' }}>{unchangedCount} unchanged</span>
                    <button
                        onClick={() => navigator.clipboard.writeText(improved)}
                        style={{ marginLeft: 'auto', fontSize: '0.6rem', padding: '0.15rem 0.5rem', borderRadius: '4px', border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', color: '#64748b' }}
                    >
                        Copy Code
                    </button>
                </div>

                {/* Diff Lines */}
                {diffLines.map((dl, i) => (
                    <span key={i} style={{
                        display: 'flex',
                        backgroundColor:
                            dl.type === 'added' ? 'rgba(34, 197, 94, 0.12)' : 'transparent',
                        borderLeft: dl.type === 'added'
                            ? '3px solid #22c55e'
                            : '3px solid transparent',
                    }}>
                        {/* Line number gutter */}
                        <span style={{
                            minWidth: '36px',
                            textAlign: 'right',
                            paddingRight: '8px',
                            color: dl.type === 'added' ? '#16a34a' : '#94a3b8',
                            userSelect: 'none',
                            fontSize: '0.65rem',
                            lineHeight: 1.6,
                            fontFamily: 'Consolas, Monaco, monospace',
                        }}>
                            {dl.type === 'added' ? '+' : ''}{dl.lineNo}
                        </span>
                        {/* Code content */}
                        <span style={{
                            flex: 1,
                            paddingLeft: '4px',
                            color: dl.type === 'added' ? '#14532d' : '#1e293b',
                            fontWeight: dl.type === 'added' ? 600 : 400,
                        }}>
                            {dl.line || '\u00A0'}
                        </span>
                    </span>
                ))}
            </>
        );
    };


    const renderTransactionTable = (title: string, icon: React.ReactNode, type: 'code' | 'llm') => {
        if (!logicData?.reconciliation) return null;

        const { matched_pairs, field_flags, unmatched_code, unmatched_llm } = logicData.reconciliation;

        // Build rows: matched + unmatched
        interface RowData {
            t: Transaction;
            flags: FieldFlags;
            status: 'matched' | 'missing_in_llm' | 'missing_in_code';
            score?: number;
            descSim?: number;
            id: string;
            codeTxn?: any;
        }

        const rows: RowData[] = [];

        // Matched pairs
        matched_pairs.forEach((pair, idx) => {
            const f = field_flags[idx] || {};
            rows.push({
                t: type === 'code' ? pair.code : pair.llm,
                flags: f,
                status: 'matched',
                score: pair.score,
                descSim: pair.desc_similarity,
                id: `matched_${type}_${idx}`,
                codeTxn: pair.code,
            });
        });

        // Unmatched
        if (type === 'code') {
            unmatched_code.forEach((t, idx) => {
                rows.push({ t, flags: {}, status: 'missing_in_llm', id: `unmatched_code_${idx}` });
            });
        } else {
            unmatched_llm.forEach((t, idx) => {
                rows.push({ t, flags: {}, status: 'missing_in_code', id: `unmatched_llm_${idx}` });
            });
        }

        const matchedCount = matched_pairs.length;
        const unmatchedRows = rows.filter(r => r.status !== 'matched');
        const acceptedInThisTable = unmatchedRows.filter(r => acceptedTxns.has(r.id)).length;
        const realUnmatchedCount = unmatchedRows.length - acceptedInThisTable;

        return (
            <div className="triple-panel">
                <div className="panel-header" style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)', marginBottom: 0 }}>
                    {icon}
                    <span style={{ fontSize: '0.9rem' }}>{title}</span>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem' }}>
                        <span className="badge" style={{ background: '#d1fae520', color: '#10b981', fontSize: '0.65rem' }}>
                            {matchedCount + acceptedInThisTable} matched{acceptedInThisTable > 0 ? ` (${acceptedInThisTable} accepted)` : ''}
                        </span>
                        {realUnmatchedCount > 0 && (
                            <span className="badge" style={{ background: '#fee2e220', color: '#ef4444', fontSize: '0.65rem' }}>
                                {realUnmatchedCount} unmatched
                            </span>
                        )}
                        
                        {/* New 'Set Code as Truth' button in the Code panel header */}
                        {type === 'code' && (
                                    <button
                                        onClick={() => {
                                            handleRemarkChange('global_empty', 'VERIFIED TRUTH: The current code output is 100% correct for this document. Use this as a Golden Target to optimize and generalize the logic further. Add better error handling but keep the core regex.');
                                        }}
                                        style={{
                                            marginLeft: '0.5rem',
                                            padding: '0.2rem 0.6rem',
                                            fontSize: '0.65rem',
                                            fontWeight: 700,
                                            borderRadius: '6px',
                                            border: '1px solid #10b981',
                                            background: '#fff',
                                            color: '#10b981',
                                            cursor: 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '0.3rem',
                                            transition: 'all 0.2s ease',
                                        }}
                                        title="Trust this code: Sets a global remark confirming this extraction is correct for future Generate clicks."
                                    >
                                        <CheckCircle2 size={10} />
                                        Set Code as Truth
                                    </button>
                        )}
                    </div>
                </div>
                <div className="panel-content">
                    {rows.length === 0 ? (
                        <div style={{ padding: '2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                            <div style={{ opacity: 0.5, fontSize: '0.8rem' }}>No transactions found.</div>
                            {type === 'llm' && (
                                <button
                                    onClick={handleRunLLM}
                                    disabled={isRunningLLM}
                                    style={{
                                        padding: '0.5rem 1rem',
                                        fontSize: '0.75rem',
                                        borderRadius: '8px',
                                        background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                                        color: '#fff',
                                        border: 'none',
                                        cursor: isRunningLLM ? 'not-allowed' : 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem',
                                        boxShadow: '0 4px 12px rgba(99,102,241,0.2)'
                                    }}
                                >
                                    {isRunningLLM ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
                                    {isRunningLLM ? 'Extracting...' : 'Run LLM Extraction Now'}
                                </button>
                            )}

                            {/* Edge Case: Both LLM and Code completely failed */}
                            {type === 'code' && (
                                <div style={{ marginTop: '1rem', width: '100%', maxWidth: '400px', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>If both completely missed a transaction format in the PDF, type a hint here:</span>
                                    <input
                                        type="text"
                                        placeholder="E.g., Missing table starting at page 2, column 'Withdrawals' is debit..."
                                        value={remarks['global_empty'] || ''}
                                        onChange={(e) => handleRemarkChange('global_empty', e.target.value)}
                                        style={{
                                            border: '1px solid var(--border-color)',
                                            borderRadius: '6px',
                                            fontSize: '0.75rem',
                                            padding: '0.5rem',
                                            width: '100%',
                                        }}
                                    />
                                </div>
                            )}
                        </div>
                    ) : (
                        <table className="mini-table">
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Details</th>
                                    <th>Amount</th>
                                    <th>Status / Flags</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map(({ t, flags, status, score, descSim, id, codeTxn }) => {
                                    // Merge auto flags with manual overrides
                                    const mf = manualFlags[id] || {};
                                    const effectiveFlags: FieldFlags = {
                                        date_mismatch: mf.date_mismatch !== undefined ? mf.date_mismatch : flags.date_mismatch,
                                        amount_mismatch: mf.amount_mismatch !== undefined ? mf.amount_mismatch : flags.amount_mismatch,
                                        detail_mismatch: mf.detail_mismatch !== undefined ? mf.detail_mismatch : flags.detail_mismatch,
                                    };

                                    const isUnmatched = status !== 'matched';
                                    const isAccepted = acceptedTxns.has(id);

                                    return (
                                        <tr key={id} style={{ opacity: isAccepted ? 0.7 : 1 }}>
                                            <td style={{ whiteSpace: 'nowrap', ...cellHighlight(!!effectiveFlags.date_mismatch) }}>
                                                {t.date}
                                            </td>
                                            <td style={{ minWidth: '100px', ...cellHighlight(!!effectiveFlags.detail_mismatch) }}>
                                                {t.details}
                                            </td>
                                            <td style={{ fontWeight: 600, ...cellHighlight(!!effectiveFlags.amount_mismatch) }}>
                                                {t.credit ? (
                                                    <span style={{ color: '#10b981' }}>+{t.credit}</span>
                                                ) : t.debit ? (
                                                    <span style={{ color: '#f87171' }}>-{t.debit}</span>
                                                ) : '0.00'}
                                            </td>
                                            <td style={{ fontSize: '0.7rem' }}>
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                                    {/* Status badge */}
                                                    {isUnmatched ? (
                                                        <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', flexWrap: 'wrap' }}>
                                                            {isAccepted ? (
                                                                <span style={{ fontSize: '0.6rem', color: '#10b981', background: '#d1fae5', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                                                                    ✓ Accepted
                                                                </span>
                                                            ) : (
                                                                <span style={{ fontSize: '0.6rem', color: '#ef4444', background: '#fee2e2', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                                                                    {status === 'missing_in_llm' ? '⚠ Missing in LLM' : '⚠ Missing in Code'}
                                                                </span>
                                                            )}
                                                            <button
                                                                onClick={() => toggleAccept(id)}
                                                                style={{
                                                                    fontSize: '0.55rem',
                                                                    padding: '0.1rem 0.4rem',
                                                                    borderRadius: '4px',
                                                                    border: '1px solid',
                                                                    cursor: 'pointer',
                                                                    borderColor: isAccepted ? '#10b981' : '#cbd5e1',
                                                                    background: isAccepted ? '#d1fae5' : '#fff',
                                                                    color: isAccepted ? '#10b981' : '#64748b',
                                                                }}
                                                            >
                                                                {isAccepted ? '✓ Accepted' : 'Accept ✓'}
                                                            </button>
                                                            
                                                            {/* Case 1: missing_in_llm (Code has it, LLM doesn't) -> Trust Code button */}
                                                            {status === 'missing_in_llm' && type === 'code' && (
                                                                <button
                                                                    onClick={() => {
                                                                        handleRemarkChange(id, '[TRUST_CODE]: Code side is correct. The LLM baseline missed this row entirely.');
                                                                        if (!acceptedTxns.has(id)) toggleAccept(id);
                                                                    }}
                                                                    style={{ fontSize: '0.55rem', padding: '0.1rem 0.5rem', background: '#10b981', color: '#fff', borderRadius: '4px', border: 'none', cursor: 'pointer', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                                                                    title="Tell the Code Generator that this extra row is actually correct and Code is the source of truth."
                                                                >
                                                                    <CheckCircle2 size={10} /> Trust Code
                                                                </button>
                                                            )}
                                                            
                                                            {/* Case 2: missing_in_code (LLM has it, Code doesn't) -> Trust LLM button */}
                                                            {status === 'missing_in_code' && type === 'llm' && (
                                                                <button
                                                                    onClick={() => {
                                                                        handleRemarkChange(id, '[TRUST_LLM]: LLM baseline is correct. The code logic failed to extract this row. Fix code to match LLM.');
                                                                        if (!acceptedTxns.has(id)) toggleAccept(id);
                                                                    }}
                                                                    style={{ fontSize: '0.55rem', padding: '0.1rem 0.5rem', background: '#6366f1', color: '#fff', borderRadius: '4px', border: 'none', cursor: 'pointer', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                                                                    title="Tell the Code Generator that the LLM baseline is correct and Code logic needs to be fixed to catch this."
                                                                >
                                                                    <Cpu size={10} /> Trust LLM
                                                                </button>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', alignItems: 'center' }}>
                                                            <span style={{ fontSize: '0.6rem', color: '#10b981', background: '#d1fae5', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                                                                ✓ Score: {score} | Desc: {descSim}%
                                                            </span>
                                                            {type === 'llm' && codeTxn && (
                                                                <div style={{ display: 'flex', gap: '0.2rem' }}>
                                                                    <button
                                                                        onClick={() => {
                                                                            handleRemarkChange(id, '[TRUST_CODE]: Code side is correct. LLM baseline data is wrong for this row.');
                                                                            if (!acceptedTxns.has(id)) toggleAccept(id);
                                                                        }}
                                                                        style={{ fontSize: '0.55rem', padding: '0.1rem 0.5rem', background: '#10b981', color: '#fff', borderRadius: '4px', border: 'none', cursor: 'pointer', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                                                                        title="Trust the Code values for this row mismatch."
                                                                    >
                                                                        <CheckCircle2 size={10} /> Trust Code
                                                                    </button>
                                                                    <button
                                                                        onClick={() => {
                                                                            handleRemarkChange(id, '[TRUST_LLM]: LLM baseline is correct. Code logic extracted wrong values for this row.');
                                                                            if (!acceptedTxns.has(id)) toggleAccept(id);
                                                                        }}
                                                                        style={{ fontSize: '0.55rem', padding: '0.1rem 0.5rem', background: '#6366f1', color: '#fff', borderRadius: '4px', border: 'none', cursor: 'pointer', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                                                                        title="Trust the LLM values for this row mismatch. Fix code to match LLM."
                                                                    >
                                                                        <Cpu size={10} /> Trust LLM
                                                                    </button>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Field-level flag toggles */}
                                                    {status === 'matched' && (
                                                        <div style={{ display: 'flex', gap: '0.2rem', flexWrap: 'wrap' }}>
                                                            {(['date_mismatch', 'amount_mismatch', 'detail_mismatch'] as const).map(fk => (
                                                                <button
                                                                    key={fk}
                                                                    onClick={() => toggleFlag(id, fk)}
                                                                    style={{
                                                                        fontSize: '0.55rem',
                                                                        padding: '0.1rem 0.3rem',
                                                                        borderRadius: '3px',
                                                                        border: '1px solid',
                                                                        cursor: 'pointer',
                                                                        borderColor: effectiveFlags[fk] ? '#ef4444' : '#cbd5e1',
                                                                        background: effectiveFlags[fk] ? '#fee2e2' : '#f8fafc',
                                                                        color: effectiveFlags[fk] ? '#ef4444' : '#94a3b8',
                                                                    }}
                                                                >
                                                                    {fk.replace('_', ' ')}
                                                                </button>
                                                            ))}
                                                        </div>
                                                    )}

                                                    {/* Editable remark */}
                                                    <input
                                                        type="text"
                                                        placeholder="Add remark..."
                                                        value={remarks[id] || ''}
                                                        onChange={(e) => handleRemarkChange(id, e.target.value)}
                                                        style={{
                                                            border: '1px solid var(--border-color)',
                                                            borderRadius: '4px',
                                                            fontSize: '0.65rem',
                                                            padding: '0.15rem 0.3rem',
                                                            width: '100%',
                                                            background: 'rgba(255,255,255,0.5)',
                                                        }}
                                                    />
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className="page-container" style={{ maxWidth: '1700px' }}>
            <div className="glass-card" style={{ textAlign: 'left', padding: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
                    <div className="icon-wrapper" style={{ marginBottom: 0, width: '60px', height: '60px' }}>
                        <FileCheck size={30} />
                    </div>
                    <div>
                        <h1 className="page-title" style={{ fontSize: '2rem', marginBottom: '0.25rem' }}>Review Documents</h1>
                        <p className="page-subtitle" style={{ margin: 0 }}>
                            Showing documents with <span style={{ color: '#f59e0b' }}>EXPERIMENTAL</span> format status.
                        </p>
                    </div>
                </div>

                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                        <Loader2 className="animate-spin" size={40} color="#6366f1" />
                    </div>
                ) : error ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#f87171' }}>
                        <p>{error}</p>
                    </div>
                ) : (
                    <>
                        <div className="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Stmt ID</th>
                                        <th>Doc ID</th>
                                        <th>User ID</th>
                                        <th>Type</th>
                                        <th>Institution</th>
                                        <th>Doc Status</th>
                                        <th>Format Status</th>
                                        <th>Parsed By</th>
                                        <th>QC Result</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {documents.map((doc) => (
                                        <tr
                                            key={doc.document_id}
                                            onClick={() => handleRowClick(doc.document_id)}
                                            className={selectedDocId === doc.document_id ? 'selected' : ''}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <td>{doc.statement_id}</td>
                                            <td>{doc.document_id}</td>
                                            <td>{doc.user_id}</td>
                                            <td>{doc.statement_type}</td>
                                            <td>{doc.institution_name}</td>
                                            <td><span className="badge badge-parsed">{doc.doc_status}</span></td>
                                            <td><span className="badge badge-review">{doc.format_status}</span></td>
                                            <td><span className="badge badge-parsed">{doc.transaction_parsed_type || 'N/A'}</span></td>
                                            <td>
                                                {doc.is_auto_flagged > 0 ? (
                                                    <span className="badge" style={{
                                                        background: '#fee2e2',
                                                        color: '#ef4444',
                                                        border: '1px solid #fecaca',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '4px',
                                                        fontSize: '0.7rem'
                                                    }}>
                                                        <AlertTriangle size={12} />
                                                        AUTO-FLAGGED ({doc.last_qc_accuracy}%)
                                                    </span>
                                                ) : doc.last_qc_accuracy !== null ? (
                                                    <span className="badge" style={{
                                                        background: '#f0fdf4',
                                                        color: '#16a34a',
                                                        border: '1px solid #bbf7d0',
                                                        fontSize: '0.7rem'
                                                    }}>
                                                        PASSED ({doc.last_qc_accuracy}%)
                                                    </span>
                                                ) : (
                                                    <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>No QC yet</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {selectedDocId && (
                            <>
                                {/* Overall Similarity Banner */}
                                {logicData?.reconciliation && (
                                    <>
                                    <div style={{
                                        margin: '1.5rem 0',
                                        padding: '1rem 1.5rem',
                                        borderRadius: '12px',
                                        background: 'linear-gradient(135deg, rgba(99,102,241,0.05), rgba(139,92,246,0.05))',
                                        border: '1px solid rgba(99,102,241,0.15)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '2rem',
                                        animation: 'fadeIn 0.4s ease-out',
                                    }}>
                                        {/* Big similarity circle */}
                                        <div style={{
                                            width: '80px',
                                            height: '80px',
                                            borderRadius: '50%',
                                            background: `conic-gradient(${logicData.reconciliation.overall_similarity >= 80 ? '#10b981' :
                                                logicData.reconciliation.overall_similarity >= 50 ? '#f59e0b' : '#ef4444'
                                                } ${logicData.reconciliation.overall_similarity * 3.6}deg, #e2e8f0 0deg)`,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            flexShrink: 0,
                                        }}>
                                            <div style={{
                                                width: '64px',
                                                height: '64px',
                                                borderRadius: '50%',
                                                background: 'white',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                flexDirection: 'column',
                                            }}>
                                                <span style={{
                                                    fontSize: '1.2rem',
                                                    fontWeight: 700,
                                                    color: logicData.reconciliation.overall_similarity >= 80 ? '#10b981' :
                                                        logicData.reconciliation.overall_similarity >= 50 ? '#f59e0b' : '#ef4444',
                                                    lineHeight: 1,
                                                }}>
                                                    {logicData.reconciliation.overall_similarity}%
                                                </span>
                                            </div>
                                        </div>

                                        {/* Label */}
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontSize: '1rem', fontWeight: 600, color: '#1e293b', marginBottom: '0.3rem' }}>
                                                Overall Similarity
                                            </div>
                                            <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                                Symmetric reconciliation between Code and LLM extraction
                                            </div>
                                        </div>

                                        {/* Override & Improve Button */}
                                    </div>

                                    {/* Summary metrics */}
                                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                                        {[
                                            { label: 'Code', value: logicData.reconciliation.summary.total_code, color: '#10b981' },
                                            { label: 'LLM', value: logicData.reconciliation.summary.total_llm, color: '#8b5cf6' },
                                            { label: 'Matched', value: logicData.reconciliation.summary.matched_count, color: '#3b82f6' },
                                            { label: 'Accepted', value: acceptedTxns.size, color: '#f59e0b' },
                                            { label: 'Unmatched', value: Math.max(0, logicData.reconciliation.summary.unmatched_code_count + logicData.reconciliation.summary.unmatched_llm_count - acceptedTxns.size), color: '#ef4444' },
                                        ].map(m => (
                                            <div key={m.label} style={{ textAlign: 'center', minWidth: '55px' }}>
                                                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: m.color }}>{m.value}</div>
                                                <div style={{ fontSize: '0.6rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{m.label}</div>
                                            </div>
                                        ))}

                                        <div style={{ flex: 1 }} />

                                        {/* Bulk Trust Actions Column */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', borderLeft: '1px solid var(--border-color)', paddingLeft: '1rem' }}>
                                            <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 600 }}>BULK TRUST (SAVE TIME)</div>
                                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                                <button
                                                    onClick={() => handleTrustAllMatches('code')}
                                                    style={{
                                                        padding: '0.3rem 0.6rem',
                                                        fontSize: '0.65rem',
                                                        borderRadius: '6px',
                                                        border: `1px solid ${trustAllMatchesAs === 'code' ? '#10b981' : '#e2e8f0'}`,
                                                        background: trustAllMatchesAs === 'code' ? '#f0fdf4' : '#fff',
                                                        color: trustAllMatchesAs === 'code' ? '#16a34a' : '#64748b',
                                                        fontWeight: 700,
                                                        cursor: 'pointer'
                                                    }}
                                                >
                                                    {trustAllMatchesAs === 'code' && <Check size={10} style={{ marginRight: '3px' }} />}
                                                    Trust All Matches as Code
                                                </button>
                                                <button
                                                    onClick={() => handleTrustAllMatches('llm')}
                                                    style={{
                                                        padding: '0.3rem 0.6rem',
                                                        fontSize: '0.65rem',
                                                        borderRadius: '6px',
                                                        border: `1px solid ${trustAllMatchesAs === 'llm' ? '#8b5cf6' : '#e2e8f0'}`,
                                                        background: trustAllMatchesAs === 'llm' ? '#f5f3ff' : '#fff',
                                                        color: trustAllMatchesAs === 'llm' ? '#7c3aed' : '#64748b',
                                                        fontWeight: 700,
                                                        cursor: 'pointer'
                                                    }}
                                                >
                                                    {trustAllMatchesAs === 'llm' && <Check size={10} style={{ marginRight: '3px' }} />}
                                                    Trust All Matches as LLM
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    </>
                                )}

                                <div className="details-grid">
                                    <div className="editor-panel">
                                        <div className="panel-header">
                                            <Code2 size={20} color="#fbbf24" />
                                            Extraction Logic
                                        </div>
                                        {isFetchingLogic ? (
                                            <div className="code-editor" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                <Loader2 className="animate-spin" size={30} color="#fbbf24" />
                                            </div>
                                        ) : (
                                            <textarea className="code-editor" readOnly value={logicData?.extraction_logic || '# No logic available.'} />
                                        )}
                                    </div>

                                    <div className="editor-panel" style={{ borderRadius: '12px', display: 'flex', flexDirection: 'column' }}>
                                        <div className="panel-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <Wand2 size={20} color="#8b5cf6" />
                                            Improved Code
                                            <button
                                                onClick={handleGenerateImprovedCode}
                                                disabled={isGenerating || !logicData}
                                                style={{
                                                    marginLeft: 'auto',
                                                    padding: '0.3rem 0.7rem',
                                                    fontSize: '0.7rem',
                                                    borderRadius: '6px',
                                                    border: 'none',
                                                    background: isGenerating ? '#94a3b8' : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                                                    color: '#fff',
                                                    cursor: isGenerating ? 'not-allowed' : 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.3rem',
                                                }}
                                            >
                                                {isGenerating ? <Loader2 className="animate-spin" size={12} /> : <Wand2 size={12} />}
                                                {isGenerating ? 'Generating...' : 'Generate'}
                                            </button>
                                        </div>

                                        {!improvedCode && !isGenerating && (
                                            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.4, flexDirection: 'column', gap: '0.5rem', padding: '2rem' }}>
                                                <Wand2 size={36} />
                                                <p style={{ fontSize: '0.8rem', textAlign: 'center' }}>Click "Generate" to send QC feedback to the LLM and get improved extraction code.</p>
                                            </div>
                                        )}

                                        {isGenerating && (
                                            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '0.5rem' }}>
                                                <Loader2 className="animate-spin" size={30} color="#8b5cf6" />
                                                <p style={{ fontSize: '0.75rem', opacity: 0.6 }}>LLM is analyzing feedback & generating improved code...</p>
                                            </div>
                                        )}

                                        {improvedCode && !isGenerating && (
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                                                <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
                                                    <pre style={{
                                                        margin: 0,
                                                        padding: 0,
                                                        fontSize: '0.7rem',
                                                        fontFamily: 'Consolas, Monaco, monospace',
                                                        lineHeight: 1.6,
                                                        whiteSpace: 'pre-wrap',
                                                        wordBreak: 'break-word',
                                                        background: '#fafaf9',
                                                        color: '#1e293b',
                                                        borderRadius: '0 0 8px 8px',
                                                        border: '1px solid #e2e8f0',
                                                        overflow: 'auto',
                                                    }}>
                                                        {renderDiffCode(originalCode, improvedCode)}
                                                    </pre>
                                                </div>
                                                <div style={{ padding: '0.5rem 0.75rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                    <button
                                                        onClick={handleRunImprovedCode}
                                                        disabled={isRunning}
                                                        style={{
                                                            padding: '0.35rem 0.8rem',
                                                            fontSize: '0.7rem',
                                                            borderRadius: '6px',
                                                            border: 'none',
                                                            background: isRunning ? '#94a3b8' : 'linear-gradient(135deg, #10b981, #059669)',
                                                            color: '#fff',
                                                            cursor: isRunning ? 'not-allowed' : 'pointer',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: '0.3rem',
                                                        }}
                                                    >
                                                        {isRunning ? <Loader2 className="animate-spin" size={12} /> : <Play size={12} />}
                                                        {isRunning ? 'Running...' : 'Re-run Improved Code'}
                                                    </button>
                                                    {runResult && !runResult.error && (
                                                        <span style={{ fontSize: '0.65rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                                                            <CheckCircle2 size={12} /> {runResult.transaction_count} txns
                                                        </span>
                                                    )}
                                                    {runResult?.error && (
                                                        <span style={{ fontSize: '0.65rem', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                                                            <AlertTriangle size={12} /> {runResult.error}
                                                        </span>
                                                    )}

                                                    {/* Accuracy Score */}
                                                    {runResult && !runResult.error && runResult.reconciliation?.overall_similarity != null && (
                                                        <span style={{
                                                            fontSize: '0.65rem',
                                                            fontWeight: 700,
                                                            padding: '0.15rem 0.5rem',
                                                            borderRadius: '6px',
                                                            background: runResult.reconciliation.overall_similarity >= 95 ? '#d1fae5' :
                                                                runResult.reconciliation.overall_similarity >= 80 ? '#fef3c7' : '#fee2e2',
                                                            color: runResult.reconciliation.overall_similarity >= 95 ? '#059669' :
                                                                runResult.reconciliation.overall_similarity >= 80 ? '#d97706' : '#dc2626',
                                                        }}>
                                                            Accuracy: {runResult.reconciliation.overall_similarity}%
                                                        </span>
                                                    )}

                                                    {/* Strict Save Button — only allows save if >= 95% */}
                                                    {runResult && !runResult.error && runResult.reconciliation?.overall_similarity != null && (
                                                        <>
                                                        <button
                                                            onClick={() => handleSaveImprovedCode(false)}
                                                            disabled={isSaving || saveStatus === 'saved' || runResult.reconciliation.overall_similarity < 95}
                                                            style={{
                                                                padding: '0.35rem 0.8rem',
                                                                fontSize: '0.7rem',
                                                                borderRadius: '6px',
                                                                border: 'none',
                                                                background: saveStatus === 'saved' ? '#d1fae5' :
                                                                    isSaving ? '#94a3b8' :
                                                                        runResult.reconciliation.overall_similarity >= 95 ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : '#cbd5e1',
                                                                color: saveStatus === 'saved' ? '#059669' : runResult.reconciliation.overall_similarity >= 95 ? '#fff' : '#64748b',
                                                                cursor: (isSaving || saveStatus === 'saved' || runResult.reconciliation.overall_similarity < 95) ? 'not-allowed' : 'pointer',
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                gap: '0.3rem',
                                                                marginLeft: 'auto',
                                                            }}
                                                        >
                                                            {isSaving ? <Loader2 className="animate-spin" size={12} /> : saveStatus === 'saved' ? <CheckCircle2 size={12} /> : <Save size={12} />}
                                                            {isSaving ? 'Saving...' : saveStatus === 'saved' ? 'Saved!' : 'Save Code'}
                                                        </button>

                                                        {/* Force Save Button — bypasses accuracy threshold */}
                                                        {runResult.reconciliation.overall_similarity < 95 && forceSaveStatus !== 'saved' && saveStatus !== 'saved' && (
                                                            <button
                                                                onClick={handleForceSaveImprovedCode}
                                                                disabled={isForceSaving}
                                                                style={{
                                                                    padding: '0.35rem 0.8rem',
                                                                    fontSize: '0.7rem',
                                                                    borderRadius: '6px',
                                                                    border: 'none',
                                                                    background: isForceSaving ? '#94a3b8' : 'linear-gradient(135deg, #f59e0b, #d97706)',
                                                                    color: '#fff',
                                                                    cursor: isForceSaving ? 'not-allowed' : 'pointer',
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    gap: '0.3rem',
                                                                    fontWeight: 600,
                                                                }}
                                                                title="Force save this code even though accuracy is below 95%. Use with caution."
                                                            >
                                                                {isForceSaving ? <Loader2 className="animate-spin" size={12} /> : <AlertTriangle size={12} />}
                                                                {isForceSaving ? 'Force Saving...' : 'Force Save Code'}
                                                            </button>
                                                        )}
                                                        {forceSaveStatus === 'saved' && (
                                                            <span style={{ fontSize: '0.65rem', color: '#059669', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                                                                <CheckCircle2 size={12} /> Force Saved!
                                                            </span>
                                                        )}
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="bottom-grid">
                                    {/* PDF Viewer */}
                                    <div className="triple-panel">
                                        <div className="panel-header" style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)', marginBottom: 0 }}>
                                            <FileText size={20} color="#6366f1" />
                                            <span style={{ fontSize: '0.9rem' }}>PDF Original</span>
                                        </div>
                                        <div className="panel-content" style={{ padding: 0 }}>
                                            {pdfBlobUrl ? (
                                                <iframe
                                                    className="pdf-viewer"
                                                    src={pdfBlobUrl}
                                                    title="PDF Preview"
                                                />
                                            ) : pdfError ? (
                                                <div style={{
                                                    display: 'flex', flexDirection: 'column', alignItems: 'center',
                                                    justifyContent: 'center', height: '100%', gap: '0.75rem',
                                                    padding: '1.5rem', textAlign: 'center',
                                                }}>
                                                    <FileText size={36} color="#94a3b8" />
                                                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b' }}>
                                                        PDF not available
                                                    </span>
                                                    <span style={{
                                                        fontSize: '0.7rem', color: '#94a3b8',
                                                        background: '#f1f5f9', borderRadius: '6px',
                                                        padding: '0.4rem 0.75rem', maxWidth: '100%',
                                                        wordBreak: 'break-all',
                                                    }}>
                                                        {pdfError}
                                                    </span>
                                                    <span style={{ fontSize: '0.65rem', color: '#10b981' }}>
                                                        Transaction data is still available →
                                                    </span>
                                                </div>
                                            ) : isFetchingLogic ? (
                                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '0.5rem', opacity: 0.5 }}>
                                                    <Loader2 className="animate-spin" size={20} />
                                                    <span style={{ fontSize: '0.8rem' }}>Loading PDF...</span>
                                                </div>
                                            ) : (
                                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.4, fontSize: '0.8rem' }}>
                                                    Select a document to preview
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Code Extraction Table */}
                                    {renderTransactionTable(
                                        "Code Extraction",
                                        <Cpu size={20} color="#10b981" />,
                                        "code"
                                    )}

                                    {/* LLM Extraction Table */}
                                    {renderTransactionTable(
                                        "LLM Extraction",
                                        <Sparkles size={20} color="#8b5cf6" />,
                                        "llm"
                                    )}
                                </div>

                                {/* Improved Code Transactions - shown after re-run */}
                                {runResult && !runResult.error && runResult.new_transactions.length > 0 && (
                                    <div style={{ marginTop: '2rem', animation: 'fadeIn 0.4s ease-out' }}>
                                        <div className="triple-panel" style={{ maxHeight: '500px' }}>
                                            <div className="panel-header" style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)', marginBottom: 0 }}>
                                                <Wand2 size={20} color="#f59e0b" />
                                                <span style={{ fontSize: '0.9rem' }}>Improved Code Transactions</span>
                                                <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem' }}>
                                                    <span className="badge" style={{ background: '#fef3c720', color: '#f59e0b', fontSize: '0.65rem' }}>
                                                        {runResult.transaction_count} extracted
                                                    </span>
                                                    {runResult.reconciliation && (
                                                        <>
                                                            <span className="badge" style={{ background: '#d1fae520', color: '#10b981', fontSize: '0.65rem' }}>
                                                                {runResult.reconciliation.matched_pairs?.length || 0} matched
                                                            </span>
                                                            {(runResult.reconciliation.unmatched_code?.length > 0 || runResult.reconciliation.unmatched_llm?.length > 0) && (
                                                                <span className="badge" style={{ background: '#fee2e220', color: '#ef4444', fontSize: '0.65rem' }}>
                                                                    {(runResult.reconciliation.unmatched_code?.length || 0) + (runResult.reconciliation.unmatched_llm?.length || 0)} unmatched
                                                                </span>
                                                            )}
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="panel-content" style={{ overflow: 'auto' }}>
                                                <table className="mini-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Date</th>
                                                            <th>Details</th>
                                                            <th>Amount</th>
                                                            <th>Status</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {/* Matched transactions */}
                                                        {runResult.reconciliation?.matched_pairs?.map((pair: any, idx: number) => {
                                                            const flags = runResult.reconciliation.field_flags?.[idx] || {};
                                                            const t = pair.code;
                                                            return (
                                                                <tr key={`imp_match_${idx}`}>
                                                                    <td style={{ whiteSpace: 'nowrap', ...cellHighlight(!!flags.date_mismatch) }}>{t.date}</td>
                                                                    <td style={{ minWidth: '100px', ...cellHighlight(!!flags.detail_mismatch) }}>{t.details}</td>
                                                                    <td style={{ fontWeight: 600, ...cellHighlight(!!flags.amount_mismatch) }}>
                                                                        {t.credit ? (
                                                                            <span style={{ color: '#10b981' }}>+{t.credit}</span>
                                                                        ) : t.debit ? (
                                                                            <span style={{ color: '#f87171' }}>-{t.debit}</span>
                                                                        ) : '0.00'}
                                                                    </td>
                                                                    <td>
                                                                        <span style={{ fontSize: '0.6rem', color: '#10b981', background: '#d1fae5', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                                                                            ✓ Score: {pair.score} | Desc: {pair.desc_similarity}%
                                                                        </span>
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                        {/* Unmatched from new code (extra) */}
                                                        {runResult.reconciliation?.unmatched_code?.map((t: any, idx: number) => (
                                                            <tr key={`imp_extra_${idx}`} style={{ backgroundColor: 'rgba(248, 113, 113, 0.05)' }}>
                                                                <td style={{ whiteSpace: 'nowrap' }}>{t.date}</td>
                                                                <td style={{ minWidth: '100px' }}>{t.details}</td>
                                                                <td style={{ fontWeight: 600 }}>
                                                                    {t.credit ? (
                                                                        <span style={{ color: '#10b981' }}>+{t.credit}</span>
                                                                    ) : t.debit ? (
                                                                        <span style={{ color: '#f87171' }}>-{t.debit}</span>
                                                                    ) : '0.00'}
                                                                </td>
                                                                <td>
                                                                    <span style={{ fontSize: '0.6rem', color: '#ef4444', background: '#fee2e2', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                                                                        ⚠ Extra (not in LLM)
                                                                    </span>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                        {/* Unmatched from LLM (still missing) */}
                                                        {runResult.reconciliation?.unmatched_llm?.map((t: any, idx: number) => (
                                                            <tr key={`imp_miss_${idx}`} style={{ backgroundColor: 'rgba(248, 113, 113, 0.05)' }}>
                                                                <td style={{ whiteSpace: 'nowrap' }}>{t.date}</td>
                                                                <td style={{ minWidth: '100px' }}>{t.details}</td>
                                                                <td style={{ fontWeight: 600 }}>
                                                                    {t.credit ? (
                                                                        <span style={{ color: '#10b981' }}>+{t.credit}</span>
                                                                    ) : t.debit ? (
                                                                        <span style={{ color: '#f87171' }}>-{t.debit}</span>
                                                                    ) : '0.00'}
                                                                </td>
                                                                <td>
                                                                    <span style={{ fontSize: '0.6rem', color: '#f59e0b', background: '#fef3c7', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                                                                        ⚠ Still missing from code
                                                                    </span>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
