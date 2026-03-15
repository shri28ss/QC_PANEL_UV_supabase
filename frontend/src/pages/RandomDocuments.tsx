import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
    Shuffle, CheckCircle, AlertTriangle, FileText, Activity,
    BarChart3, RefreshCw, Eye, ListFilter, Play, FileCheck, HelpCircle
} from 'lucide-react';

interface QcSummary {
    total_checked: number;
    avg_accuracy: number;
    lowest_accuracy: number;
    highest_accuracy: number;
    pending_count: number;
    reviewed_count: number;
    flagged_count: number;
}

interface QcResult {
    qc_id: number;
    document_id: number;
    statement_id: number;
    file_name: string;
    institution_name: string;
    code_txn_count: number;
    llm_txn_count: number;
    matched_count: number;
    unmatched_code_count: number;
    unmatched_llm_count: number;
    accuracy: number;
    qc_status: string;
    created_at: string;
    reviewed_at: string | null;
}

interface Transaction {
    date: string;
    details: string;
    debit: number | null;
    credit: number | null;
    balance?: number | null;
}

interface MatchedPair {
    code: Transaction;
    llm: Transaction;
    score: number;
    desc_similarity: number;
}

export default function RandomDocuments() {
    const [summary, setSummary] = useState<QcSummary | null>(null);
    const [results, setResults] = useState<QcResult[]>([]);
    const [loading, setLoading] = useState(true);
    const [triggering, setTriggering] = useState(false);

    // For Detail View
    const [selectedQcId, setSelectedQcId] = useState<number | null>(null);
    const [detailData, setDetailData] = useState<any | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);

    // Filter states
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [searchQuery, setSearchQuery] = useState('');

    const fetchData = async () => {
        setLoading(true);
        try {
            const [summaryRes, resultsRes] = await Promise.all([
                axios.get('http://localhost:8000/api/random-qc-summary'),
                axios.get('http://localhost:8000/api/random-qc-results')
            ]);
            setSummary(summaryRes.data);
            setResults(resultsRes.data);
        } catch (error) {
            console.error('Error fetching QC data:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleTriggerQc = async () => {
        setTriggering(true);
        try {
            const res = await axios.post('http://localhost:8000/api/random-qc-trigger');
            alert(`Triggered! Checked ${res.data.checked} documents.`);
            fetchData();
        } catch (error) {
            console.error('Error triggering QC:', error);
            alert('Failed to trigger QC check.');
        } finally {
            setTriggering(false);
        }
    };

    const handleViewDetail = async (qcId: number, docId: number) => {
        if (selectedQcId === qcId) {
            setSelectedQcId(null);
            setDetailData(null);
            return;
        }

        setSelectedQcId(qcId);
        setLoadingDetail(true);

        if (pdfBlobUrl) {
            URL.revokeObjectURL(pdfBlobUrl);
            setPdfBlobUrl(null);
        }

        try {
            const [detailRes, pdfRes] = await Promise.all([
                axios.get(`http://localhost:8000/api/random-qc-detail/${qcId}`),
                axios.get(`http://localhost:8000/api/document-pdf/${docId}`, { responseType: 'blob' })
            ]);

            setDetailData(detailRes.data);
            const blob = new Blob([pdfRes.data], { type: 'application/pdf' });
            setPdfBlobUrl(URL.createObjectURL(blob));
        } catch (error) {
            console.error('Error fetching QC detail / PDF:', error);
        } finally {
            setLoadingDetail(false);
        }
    };

    const handleReviewSubmit = async (status: string) => {
        if (!selectedQcId) return;
        try {
            await axios.post(`http://localhost:8000/api/random-qc-review/${selectedQcId}`, {
                qc_status: status,
                reviewer_notes: "Reviewed from Dashboard",
            });
            alert('Review submitted successfully!');
            fetchData();
            setSelectedQcId(null);
        } catch (error) {
            console.error("Error submitting review:", error);
            alert('Failed to submit review.');
        }
    };

    // Derived states
    const filteredResults = results.filter(r => {
        const matchesStatus = statusFilter === 'ALL' || r.qc_status === statusFilter;
        const matchesSearch = r.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.institution_name.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesStatus && matchesSearch;
    });

    return (
        <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '1400px' }}>

            {/* Header & Controls */}
            <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.5rem 2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div className="icon-wrapper" style={{ marginBottom: 0, width: '50px', height: '50px' }}>
                        <Shuffle size={24} />
                    </div>
                    <div>
                        <h1 className="page-title" style={{ fontSize: '1.8rem', margin: 0 }}>
                            Random QC Dashboard
                        </h1>
                        <p className="page-subtitle" style={{ fontSize: '0.9rem', margin: 0 }}>
                            Audits and code verification history
                        </p>
                    </div>
                </div>

                <button
                    onClick={handleTriggerQc}
                    disabled={triggering}
                    style={{
                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                        padding: '0.75rem 1.5rem', borderRadius: '8px',
                        fontWeight: 600, color: '#fff', border: 'none',
                        cursor: triggering ? 'not-allowed' : 'pointer',
                        background: triggering ? 'rgba(99, 102, 241, 0.5)' : '#4f46e5',
                        boxShadow: triggering ? 'none' : '0 4px 12px rgba(79, 70, 229, 0.3)',
                        transition: 'all 0.2s'
                    }}
                >
                    {triggering ? <RefreshCw className="animate-spin" size={18} /> : <Play size={18} fill="currentColor" />}
                    <span>{triggering ? 'Running QC Check...' : 'Run Manual QC Check'}</span>
                </button>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem' }}>
                    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px' }}>
                        <FileCheck size={24} color="#3b82f6" style={{ marginBottom: '0.5rem' }} />
                        <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Checked</span>
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1e293b', marginTop: '0.25rem' }}>{summary.total_checked || 0}</span>
                    </div>
                    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px' }}>
                        <BarChart3 size={24} color="#6366f1" style={{ marginBottom: '0.5rem' }} />
                        <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Avg Accuracy</span>
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1e293b', marginTop: '0.25rem' }}>{summary.avg_accuracy !== null ? `${summary.avg_accuracy}%` : '-'}</span>
                    </div>
                    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px', borderBottom: '3px solid #10b981' }}>
                        <Activity size={24} color="#10b981" style={{ marginBottom: '0.5rem' }} />
                        <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Highest Score</span>
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981', marginTop: '0.25rem' }}>{summary.highest_accuracy !== null ? `${summary.highest_accuracy}%` : '-'}</span>
                    </div>
                    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px', borderBottom: '3px solid #ef4444' }}>
                        <AlertTriangle size={24} color="#ef4444" style={{ marginBottom: '0.5rem' }} />
                        <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Lowest Score</span>
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ef4444', marginTop: '0.25rem' }}>{summary.lowest_accuracy !== null ? `${summary.lowest_accuracy}%` : '-'}</span>
                    </div>
                    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px' }}>
                        <HelpCircle size={24} color="#f59e0b" style={{ marginBottom: '0.5rem' }} />
                        <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pending Review</span>
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b', marginTop: '0.25rem' }}>{summary.pending_count || 0}</span>
                    </div>
                    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px' }}>
                        <CheckCircle size={24} color="#10b981" style={{ marginBottom: '0.5rem' }} />
                        <span style={{ color: '#64748b', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Reviewed</span>
                        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981', marginTop: '0.25rem' }}>{summary.reviewed_count || 0}</span>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.5rem', borderRadius: '12px' }}>
                <ListFilter size={20} color="#64748b" />
                <span style={{ color: '#475569', fontWeight: 600, fontSize: '0.9rem' }}>Filter History:</span>

                <select
                    value={statusFilter}
                    onChange={e => setStatusFilter(e.target.value)}
                    style={{
                        padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border-color)',
                        background: '#fff', color: '#1e293b', fontSize: '0.85rem', outline: 'none'
                    }}
                >
                    <option value="ALL">All Statuses</option>
                    <option value="PENDING">Pending Review</option>
                    <option value="REVIEWED">Reviewed</option>
                    <option value="FLAGGED">Flagged</option>
                </select>

                <input
                    type="text"
                    placeholder="Search Document or Bank..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    style={{
                        padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border-color)',
                        background: '#fff', color: '#1e293b', fontSize: '0.85rem', width: '250px', outline: 'none'
                    }}
                />
            </div>

            {/* Results Table */}
            <div className="table-wrapper">
                <table style={{ width: '100%' }}>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Document Name</th>
                            <th>Code Txns</th>
                            <th>LLM Txns</th>
                            <th>Accuracy</th>
                            <th>QC Status</th>
                            <th style={{ textAlign: 'right' }}>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>Loading QC Results...</td></tr>}
                        {!loading && filteredResults.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>No QC checks found.</td></tr>}

                        {!loading && filteredResults.map((row) => (
                            <React.Fragment key={row.qc_id}>
                                <tr className={selectedQcId === row.qc_id ? 'selected' : ''}>
                                    <td style={{ whiteSpace: 'nowrap' }}>
                                        {new Date(row.created_at).toLocaleString()}
                                    </td>
                                    <td>
                                        <div style={{ fontWeight: 600 }}>{row.file_name}</div>
                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{row.institution_name}</div>
                                    </td>
                                    <td style={{ fontWeight: 600 }}>{row.code_txn_count}</td>
                                    <td style={{ fontWeight: 600 }}>{row.llm_txn_count}</td>
                                    <td>
                                        <div style={{
                                            display: 'inline-block', padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600,
                                            background: row.accuracy >= 95 ? '#d1fae5' : row.accuracy >= 80 ? '#fef3c7' : '#fee2e2',
                                            color: row.accuracy >= 95 ? '#059669' : row.accuracy >= 80 ? '#d97706' : '#dc2626',
                                            border: `1px solid ${row.accuracy >= 95 ? '#a7f3d0' : row.accuracy >= 80 ? '#fde68a' : '#fecaca'}`
                                        }}>
                                            {row.accuracy}%
                                        </div>
                                    </td>
                                    <td>
                                        <div style={{
                                            display: 'inline-block', padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700,
                                            background: row.qc_status === 'REVIEWED' ? '#d1fae5' : row.qc_status === 'FLAGGED' ? '#fee2e2' : '#f1f5f9',
                                            color: row.qc_status === 'REVIEWED' ? '#059669' : row.qc_status === 'FLAGGED' ? '#ef4444' : '#475569'
                                        }}>
                                            {row.qc_status}
                                        </div>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <button
                                            onClick={() => handleViewDetail(row.qc_id, row.document_id)}
                                            style={{
                                                padding: '0.4rem 0.8rem', background: '#f8fafc', color: '#475569',
                                                border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.8rem',
                                                fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.3rem'
                                            }}
                                        >
                                            <Eye size={14} />
                                            <span>{selectedQcId === row.qc_id ? 'Close' : 'View Detail'}</span>
                                        </button>
                                    </td>
                                </tr>

                                {/* DETAIL VIEW EXPANSION */}
                                {selectedQcId === row.qc_id && (
                                    <tr>
                                        <td colSpan={7} className="p-0 border-b-2 border-indigo-500/50">
                                            <div style={{ background: '#ffffff', overflow: 'hidden', boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.06)' }}>
                                                {loadingDetail ? (
                                                    <div className="p-12 text-center" style={{ color: '#64748b' }}>Loading details & PDF...</div>
                                                ) : detailData && (
                                                    <div className="p-6 space-y-4">
                                                        {/* Row 1: Professional Header with Ring Chart */}
                                                        <div style={{ background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)', padding: '20px 24px', borderRadius: 12, border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
                                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'nowrap', gap: 20 }}>
                                                                {/* Left: Ring + Info */}
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexShrink: 0 }}>
                                                                    {/* SVG Ring Chart */}
                                                                    <div style={{ position: 'relative', width: 80, height: 80, flexShrink: 0 }}>
                                                                        <svg viewBox="0 0 36 36" width="80" height="80" style={{ transform: 'rotate(-90deg)' }}>
                                                                            <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e2e8f0" strokeWidth="2.5" />
                                                                            <circle
                                                                                cx="18" cy="18" r="15.5" fill="none"
                                                                                strokeWidth="2.5"
                                                                                strokeLinecap="round"
                                                                                stroke={Number(detailData.accuracy) >= 90 ? '#10b981' : Number(detailData.accuracy) >= 70 ? '#f59e0b' : '#ef4444'}
                                                                                strokeDasharray={`${Number(detailData.accuracy) * 0.9738} 97.38`}
                                                                                style={{ transition: 'stroke-dasharray 1s ease-in-out' }}
                                                                            />
                                                                        </svg>
                                                                        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                                                                            <span style={{ fontSize: 18, fontWeight: 900, color: '#1e293b', lineHeight: 1 }}>{detailData.accuracy}%</span>
                                                                            <span style={{ fontSize: 9, color: '#64748b', marginTop: 2, textTransform: 'uppercase', letterSpacing: 1 }}>Score</span>
                                                                        </div>
                                                                    </div>
                                                                    <div>
                                                                        <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1e293b', margin: 0 }}>Reconciliation Detail</h3>
                                                                        <p style={{ fontSize: 13, color: '#64748b', margin: '4px 0 0' }}>Code vs AI extraction comparison</p>
                                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
                                                                            <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20, background: '#ecfdf5', color: '#059669', fontWeight: 600 }}>
                                                                                ✅ {detailData.reconciliation_json?.matched_pairs?.length || 0} Matched
                                                                            </span>
                                                                            <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20, background: '#fef2f2', color: '#dc2626', fontWeight: 600 }}>
                                                                                ❌ {(detailData.reconciliation_json?.unmatched_code?.length || 0) + (detailData.reconciliation_json?.unmatched_llm?.length || 0)} Unmatched
                                                                            </span>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                                {/* Review buttons */}
                                                                <div style={{ flexShrink: 0 }}>
                                                                    {detailData.qc_status !== 'PENDING' ? (
                                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 8, background: '#ecfdf5', border: '1px solid #a7f3d0' }}>
                                                                            <CheckCircle size={18} color="#059669" />
                                                                            <span style={{ color: '#059669', fontWeight: 600, fontSize: 14 }}>{detailData.qc_status}</span>
                                                                        </div>
                                                                    ) : (
                                                                        <div style={{ display: 'flex', gap: 8 }}>
                                                                            <button
                                                                                onClick={() => handleReviewSubmit('REVIEWED')}
                                                                                style={{ background: 'linear-gradient(135deg, #059669, #10b981)', color: '#fff', fontWeight: 600, padding: '10px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, boxShadow: '0 4px 12px rgba(16,185,129,0.3)', transition: 'transform 0.15s, box-shadow 0.15s' }}
                                                                                onMouseOver={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 6px 16px rgba(16,185,129,0.4)'; }}
                                                                                onMouseOut={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(16,185,129,0.3)'; }}
                                                                            >
                                                                                <CheckCircle size={16} />
                                                                                <span>Mark Reviewed</span>
                                                                            </button>
                                                                            <button
                                                                                onClick={() => handleReviewSubmit('FLAGGED')}
                                                                                style={{ background: 'linear-gradient(135deg, #dc2626, #ef4444)', color: '#fff', fontWeight: 600, padding: '10px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, boxShadow: '0 4px 12px rgba(239,68,68,0.3)', transition: 'transform 0.15s, box-shadow 0.15s' }}
                                                                                onMouseOver={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 6px 16px rgba(239,68,68,0.4)'; }}
                                                                                onMouseOut={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(239,68,68,0.3)'; }}
                                                                            >
                                                                                <AlertTriangle size={16} />
                                                                                <span>Flag Issue</span>
                                                                            </button>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        {/* Row 2: Tables side by side */}
                                                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

                                                            {/* LEFT: Matched Transactions Table */}
                                                            <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e2e8f0', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                                                                <h4 style={{ fontSize: 13, fontWeight: 600, color: '#059669', textTransform: 'uppercase', letterSpacing: '0.05em', padding: '12px 16px', borderBottom: '1px solid #e2e8f0', background: '#f0fdf4', margin: 0 }}>
                                                                    ✅ Matched Transactions ({detailData.reconciliation_json?.matched_pairs?.length || 0})
                                                                </h4>
                                                                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                                                                    <table className="w-full text-sm text-left">
                                                                        <thead style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', background: '#f8fafc', position: 'sticky', top: 0 }}>
                                                                            <tr>
                                                                                <th className="px-3 py-2">Source</th>
                                                                                <th className="px-3 py-2">Date</th>
                                                                                <th className="px-3 py-2">Debit</th>
                                                                                <th className="px-3 py-2">Credit</th>
                                                                                <th className="px-3 py-2">Details</th>
                                                                                <th className="px-3 py-2 text-right">Score</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {detailData.reconciliation_json?.matched_pairs?.map((pair: MatchedPair, idx: number) => (
                                                                                <React.Fragment key={idx}>
                                                                                    <tr style={{ borderTop: '1px solid #f1f5f9', background: '#fff' }}>
                                                                                        <td className="px-3 py-2" style={{ fontWeight: 700, color: '#2563eb', fontSize: 11 }}>CODE</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#1e293b', whiteSpace: 'nowrap' }}>{pair.code.date}</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#dc2626', fontWeight: 500 }}>{pair.code.debit || '-'}</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#16a34a', fontWeight: 500 }}>{pair.code.credit || '-'}</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#334155', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={pair.code.details}>{pair.code.details}</td>
                                                                                        <td className="px-3 py-2 text-right" rowSpan={2}>
                                                                                            <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 20, background: pair.score >= 0.95 ? '#ecfdf5' : pair.score >= 0.8 ? '#fffbeb' : '#fef2f2', color: pair.score >= 0.95 ? '#059669' : pair.score >= 0.8 ? '#d97706' : '#dc2626' }}>
                                                                                                {pair.score}
                                                                                            </span>
                                                                                        </td>
                                                                                    </tr>
                                                                                    <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                                                        <td className="px-3 py-2" style={{ fontWeight: 700, color: '#7c3aed', fontSize: 11 }}>LLM</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#64748b', whiteSpace: 'nowrap' }}>{pair.llm.date}</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#ef4444', fontWeight: 500 }}>{pair.llm.debit || '-'}</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#22c55e', fontWeight: 500 }}>{pair.llm.credit || '-'}</td>
                                                                                        <td className="px-3 py-2" style={{ color: '#64748b', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={pair.llm.details}>{pair.llm.details}</td>
                                                                                    </tr>
                                                                                </React.Fragment>
                                                                            ))}
                                                                        </tbody>
                                                                    </table>
                                                                    {(!detailData.reconciliation_json?.matched_pairs || detailData.reconciliation_json.matched_pairs.length === 0) && (
                                                                        <div style={{ color: '#94a3b8', textAlign: 'center', padding: '24px 0' }}>No matched transactions found.</div>
                                                                    )}
                                                                </div>
                                                            </div>

                                                            {/* RIGHT: Unmatched Transactions Table */}
                                                            <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #fecaca', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                                                                <h4 style={{ fontSize: 13, fontWeight: 600, color: '#dc2626', textTransform: 'uppercase', letterSpacing: '0.05em', padding: '12px 16px', borderBottom: '1px solid #fecaca', background: '#fef2f2', margin: 0 }}>
                                                                    ❌ Unmatched (Code: {detailData.reconciliation_json?.unmatched_code?.length || 0} | LLM: {detailData.reconciliation_json?.unmatched_llm?.length || 0})
                                                                </h4>
                                                                <div style={{ maxHeight: 400, overflowY: 'auto', flex: 1 }}>
                                                                    <table className="w-full text-sm text-left">
                                                                        <thead style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', background: '#fef2f2', position: 'sticky', top: 0 }}>
                                                                            <tr>
                                                                                <th className="px-3 py-2">Source</th>
                                                                                <th className="px-3 py-2">Date</th>
                                                                                <th className="px-3 py-2">Debit</th>
                                                                                <th className="px-3 py-2">Credit</th>
                                                                                <th className="px-3 py-2">Details</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {detailData.reconciliation_json?.unmatched_code?.map((txn: Transaction, idx: number) => (
                                                                                <tr key={`uc-${idx}`} style={{ borderTop: '1px solid #fef2f2', background: '#fff' }}>
                                                                                    <td className="px-3 py-2" style={{ fontWeight: 700, color: '#2563eb', fontSize: 11 }}>CODE</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#1e293b', whiteSpace: 'nowrap' }}>{txn.date}</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#dc2626' }}>{txn.debit || '-'}</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#16a34a' }}>{txn.credit || '-'}</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#334155', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={txn.details}>{txn.details}</td>
                                                                                </tr>
                                                                            ))}
                                                                            {detailData.reconciliation_json?.unmatched_llm?.map((txn: Transaction, idx: number) => (
                                                                                <tr key={`ul-${idx}`} style={{ borderTop: '1px solid #fef2f2', background: '#fff' }}>
                                                                                    <td className="px-3 py-2" style={{ fontWeight: 700, color: '#7c3aed', fontSize: 11 }}>LLM</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#64748b', whiteSpace: 'nowrap' }}>{txn.date}</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#ef4444' }}>{txn.debit || '-'}</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#22c55e' }}>{txn.credit || '-'}</td>
                                                                                    <td className="px-3 py-2" style={{ color: '#64748b', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={txn.details}>{txn.details}</td>
                                                                                </tr>
                                                                            ))}
                                                                        </tbody>
                                                                    </table>
                                                                    {(!detailData.reconciliation_json?.unmatched_code?.length && !detailData.reconciliation_json?.unmatched_llm?.length) && (
                                                                        <div style={{ color: '#94a3b8', textAlign: 'center', padding: '24px 0' }}>No unmatched transactions. 🎉</div>
                                                                    )}
                                                                </div>
                                                            </div>

                                                        </div>

                                                        {/* Row 3: PDF full width */}
                                                        <div style={{ borderRadius: 12, border: '1px solid #e2e8f0', overflow: 'hidden', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                                                            <div style={{ textAlign: 'center', padding: '10px 16px', borderBottom: '1px solid #e2e8f0', color: '#334155', fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, background: '#f8fafc' }}>
                                                                <FileText size={18} />
                                                                <span>Original Document</span>
                                                            </div>
                                                            {pdfBlobUrl ? (
                                                                <iframe
                                                                    src={pdfBlobUrl}
                                                                    style={{ width: '100%', height: 700, display: 'block', border: 'none', background: '#fff' }}
                                                                />
                                                            ) : (
                                                                <div style={{ width: '100%', height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', background: '#f8fafc' }}>
                                                                    Preview not available
                                                                </div>
                                                            )}
                                                        </div>

                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div>

        </div>
    );
}
