


import { useEffect, useState } from 'react';
import { get } from './api';
import { LineChart, BarChart, DonutChart } from './charts.jsx';

export default function DashboardTab() {

    const [summary, setSummary] = useState(null);
    const [charts, setCharts] = useState({ line: [], bar: [], donut: [] });
    const [profiles, setProfiles] = useState([]);
    const [filters, setFilters] = useState({ profile: '', range: '7d', post_id: '', post_date: '' });
    const [postIds, setPostIds] = useState([]);
    const [postDates, setPostDates] = useState([]);

    // Fetch post ids and post dates for dropdowns
    useEffect(() => {
        get('/insights/post-ids').then(setPostIds).catch(() => setPostIds([]));
        get('/insights/post-dates').then(setPostDates).catch(() => setPostDates([]));
    }, []);
    const [profileDetails, setProfileDetails] = useState(null);
    // Fetch profile details when profile changes
    useEffect(() => {
        if (!filters.profile) {
            setProfileDetails(null);
            return;
        }
        get(`/profiles/${encodeURIComponent(filters.profile)}`)
            .then(setProfileDetails)
            .catch(() => setProfileDetails(null));
    }, [filters.profile]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch profiles for filter dropdown
    useEffect(() => {
        get('/insights/profiles')
            .then(setProfiles)
            .catch(() => setProfiles([]));
    }, []);

    // Fetch dashboard data when filters change
    useEffect(() => {
        setLoading(true);
        const params = [];
        if (filters.profile) params.push(`profile=${encodeURIComponent(filters.profile)}`);
        if (filters.range) params.push(`range=${encodeURIComponent(filters.range)}`);
        if (filters.post_id) params.push(`post_id=${encodeURIComponent(filters.post_id)}`);
        if (filters.post_date) params.push(`post_date=${encodeURIComponent(filters.post_date)}`);
        const url = '/dashboard' + (params.length ? `?${params.join('&')}` : '');
        get(url)
            .then((data) => {
                setSummary(data.summary);
                setCharts(data.charts);
                setLoading(false);
            })
            .catch((err) => {
                setError('Failed to load dashboard data');
                setLoading(false);
            });
    }, [filters]);

    function handleFilterChange(e) {
        const { name, value } = e.target;
        setFilters((prev) => ({ ...prev, [name]: value }));
    }

    if (loading) {
        return <div style={{ padding: 40, textAlign: 'center' }}>Loading dashboard...</div>;
    }
    if (error) {
        return <div style={{ padding: 40, textAlign: 'center', color: 'red' }}>{error}</div>;
    }

    return (
        <div className="dashboard-container" style={{ display: 'flex', background: '#f6fafb', minHeight: '100vh' }}>
            {/* Sidebar */}
            <aside className="sidebar" style={{ width: 300, background: '#fff', borderRadius: 18, margin: 24, padding: 24, boxShadow: '0 2px 12px #0001', height: 'fit-content' }}>
                <div className="profile-section" style={{ textAlign: 'center', marginBottom: 32 }}>
                    <div className="profile-pic" style={{ width: 80, height: 80, borderRadius: '50%', background: '#ddd', margin: '0 auto 12px' }} />
                    <h3 style={{ margin: 0 }}>{profileDetails?.name || filters.profile || 'Select a profile'}</h3>
                    <span style={{ color: '#888', fontSize: 14 }}>{profileDetails?.role || ''}</span>
                    {/* Removed Edit profile button as per request */}
                </div>
                {/* Removed profile-info fields as per request */}
                {/* Removed FAVORITES section as per request */}
            </aside>

            {/* Main Dashboard */}
            <main className="dashboard-main" style={{ flex: 1, margin: 24, marginLeft: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h2 style={{ margin: 0 }}>Overview</h2>
                    <div>
                        <button style={{ background: '#fff', border: 'none', borderRadius: 8, padding: '8px 18px', marginRight: 8, boxShadow: '0 1px 4px #0001', cursor: 'pointer' }}>⭳</button>
                        <select style={{ background: '#fff', border: 'none', borderRadius: 8, padding: '8px 18px', boxShadow: '0 1px 4px #0001', cursor: 'pointer' }}>
                            <option>Last 7 days</option>
                        </select>
                    </div>
                </div>

                {/* Summary Cards */}
                {/* Filters */}
                <div style={{ display: 'flex', gap: 18, margin: '24px 0', alignItems: 'center' }}>
                    <div>
                        <label style={{ fontWeight: 500, marginRight: 8 }}>Profile:</label>
                        <select name="profile" value={filters.profile} onChange={handleFilterChange} style={{ padding: 6, borderRadius: 6, border: '1px solid #ccc' }}>
                            <option value="">All</option>
                            {profiles.map((p) => (
                                <option key={p} value={p}>{p}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label style={{ fontWeight: 500, marginRight: 8 }}>Date Range:</label>
                        <select name="range" value={filters.range} onChange={handleFilterChange} style={{ padding: 6, borderRadius: 6, border: '1px solid #ccc' }}>
                            <option value="1d">Today</option>
                            <option value="7d">Last 7 Days</option>
                            <option value="30d">Last 30 Days</option>
                        </select>
                    </div>
                    <div>
                        <label style={{ fontWeight: 500, marginRight: 8 }}>Post ID:</label>
                        <select name="post_id" value={filters.post_id} onChange={handleFilterChange} style={{ padding: 6, borderRadius: 6, border: '1px solid #ccc', minWidth: 120 }}>
                            <option value="">All</option>
                            {postIds.map((id) => (
                                <option key={id} value={id}>{id}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label style={{ fontWeight: 500, marginRight: 8 }}>Post Date:</label>
                        <select name="post_date" value={filters.post_date} onChange={handleFilterChange} style={{ padding: 6, borderRadius: 6, border: '1px solid #ccc', minWidth: 120 }}>
                            <option value="">All</option>
                            {postDates.map((date) => (
                                <option key={date} value={date}>{date}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="summary-cards" style={{ display: 'flex', gap: 18, margin: '24px 0' }}>
                    <SummaryCard label="Total Posts" value={summary.total_posts || 0} change={0} />
                    <SummaryCard label="Total Views" value={summary.total_views || 0} change={0} />
                    <SummaryCard label="Total Likes" value={summary.total_likes || 0} change={0} />
                    <SummaryCard label="Total Comments" value={summary.total_comments || 0} change={0} />
                    <SummaryCard label="Total Engagement" value={summary.total_engagement || 0} change={0} />
                </div>

                {/* Charts Row 1 */}
                <div className="charts-row" style={{ display: 'flex', gap: 18, marginBottom: 18 }}>
                    <div className="chart-card" style={{ flex: 2, background: '#fff', borderRadius: 18, boxShadow: '0 2px 12px #0001', padding: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 12 }}>Engagement Over Time</div>
                        {charts.line && charts.line.length > 0 ? (
                            <LineChart data={charts.line} />
                        ) : (
                            <div style={{ height: 180, background: '#f6fafb', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#aaa' }}>No data</div>
                        )}
                    </div>
                    <div className="chart-card" style={{ flex: 1, background: '#fff', borderRadius: 18, boxShadow: '0 2px 12px #0001', padding: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 12 }}>Engagement Distribution</div>
                        {charts.donut && charts.donut.length > 0 ? (
                            <DonutChart data={charts.donut} />
                        ) : (
                            <div style={{ height: 180, background: '#f6fafb', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#aaa' }}>No data</div>
                        )}
                    </div>
                </div>
                <div className="charts-row" style={{ display: 'flex', gap: 18, marginBottom: 18 }}>
                    <div className="chart-card" style={{ flex: 2, background: '#fff', borderRadius: 18, boxShadow: '0 2px 12px #0001', padding: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 12 }}>Views vs Likes vs Comments</div>
                        {charts.bar && charts.bar.length > 0 ? (
                            <BarChart data={charts.bar} />
                        ) : (
                            <div style={{ height: 180, background: '#f6fafb', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#aaa' }}>No data</div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}

function SummaryCard({ label, value, change }) {
    const isUp = change >= 0;
    return (
        <div className="stat-card" style={{ flex: 1, background: '#fff', borderRadius: 18, boxShadow: '0 2px 12px #0001', padding: 24 }}>
            <div className="stat-value" style={{ fontSize: 28, fontWeight: 700 }}>{value.toLocaleString()}</div>
            <div className={`stat-change ${isUp ? 'up' : 'down'}`} style={{ color: isUp ? '#2ecc71' : '#e74c3c', fontWeight: 600, fontSize: 15, margin: '6px 0' }}>
                {isUp ? '▲' : '▼'} {Math.abs(change)}%
            </div>
            <div className="stat-label" style={{ color: '#888', fontSize: 15 }}>{label}</div>
        </div>
    );
}
