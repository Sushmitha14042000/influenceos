import { useState } from 'react'
import { get } from './api'

export default function InsightsModal({ jobId, onClose }) {
    const [insights, setInsights] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    async function fetchInsights() {
        setLoading(true)
        setError('')
        try {
            // Fetch from the new DB endpoint
            const data = await get(`/insights/db/${jobId}`)
            setInsights(data)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    // Fetch on open
    useState(() => { fetchInsights() }, [])

    return (
        <div className="modal-bg" onClick={onClose}>
            <div className="modal" onClick={e => e.stopPropagation()}>
                <h3>Insights for Job {jobId}</h3>
                {loading && <div>Loading...</div>}
                {error && <div className="error">{error}</div>}
                {insights.length === 0 && !loading && !error && <div>No insights found.</div>}
                {insights.length > 0 && (
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Views</th>
                                <th>Likes</th>
                                <th>Comments</th>
                                <th>Reposts</th>
                                <th>Shares</th>
                                <th>Post URL</th>
                            </tr>
                        </thead>
                        <tbody>
                            {insights.map((insight, idx) => (
                                <tr key={idx}>
                                    <td>{
                                        typeof insight.timestamp === 'string'
                                            ? new Date(insight.timestamp).toLocaleString()
                                            : new Date(insight.timestamp * 1000).toLocaleString()
                                    }</td>
                                    <td>{insight.views}</td>
                                    <td>{
                                        insight.like_count !== undefined
                                            ? insight.like_count
                                            : (insight.likes !== undefined ? insight.likes : 0)
                                    }</td>
                                    <td>{
                                        insight.comments_count !== undefined
                                            ? insight.comments_count
                                            : (insight.comments !== undefined ? insight.comments : 0)
                                    }</td>
                                    <td>{
                                        insight.repost_count !== undefined
                                            ? insight.repost_count
                                            : (insight.reposts !== undefined ? insight.reposts : 0)
                                    }</td>
                                    <td>{
                                        insight.share_count !== undefined
                                            ? insight.share_count
                                            : (insight.shares !== undefined ? insight.shares : 0)
                                    }</td>
                                    <td><a href={insight.post_url} target="_blank" rel="noopener noreferrer">link</a></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
                <button onClick={onClose} className="btn-primary" style={{ marginTop: 16 }}>Close</button>
            </div>
        </div>
    )
}
