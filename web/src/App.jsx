import { useEffect, useMemo, useState } from 'react'
import { get, postFile, postForm, postJson } from './api'

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function DataTable({ columns, rows, emptyLabel }) {
  if (!rows.length) {
    return <div className="empty-box">{emptyLabel}</div>
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
    </div>
  )
}

export default function App() {
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [liveMode, setLiveMode] = useState(false)
  const [serverHost, setServerHost] = useState('127.0.0.1')
  const [basePort, setBasePort] = useState(4723)

  const [batches, setBatches] = useState([])
  const [devices, setDevices] = useState([])
  const [servers, setServers] = useState([])
  const [jobs, setJobs] = useState([])
  const [events, setEvents] = useState([])

  const [selectedBatch, setSelectedBatch] = useState('')
  const [selectedDevice, setSelectedDevice] = useState('')
  const [selectedDeviceIds, setSelectedDeviceIds] = useState([])
  const [activeView, setActiveView] = useState('import')
  const [activeMonitorView, setActiveMonitorView] = useState('jobs')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [search, setSearch] = useState('')

  // Virality campaign state
  const [campaigns, setCampaigns] = useState([])
  const [vCampaignName, setVCampaignName] = useState('')
  const [vTargetUrl, setVTargetUrl] = useState('')
  const [vAccounts, setVAccounts] = useState('')
  const [vWaveCount, setVWaveCount] = useState(3)
  const [vWaveGap, setVWaveGap] = useState(600)
  const [vActionMix, setVActionMix] = useState({ like: 60, comment: 20, save: 15, share: 5 })
  const [vCommentBank, setVCommentBank] = useState('Amazing! 🔥\nLove this! ❤️\nThis is incredible!\nSo good!\nAbsolutely stunning!')
  const [vLiveMode, setVLiveMode] = useState(false)
  const [selectedCampaign, setSelectedCampaign] = useState('')
  const [campaignProgress, setCampaignProgress] = useState(null)

  const selectedBatchId = useMemo(() => Number(selectedBatch || 0), [selectedBatch])
  const onlineDevices = useMemo(
    () => devices.filter((d) => d.status === 'online').map((d) => d.device_id),
    [devices]
  )

  const filteredJobs = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) {
      return jobs
    }

    return jobs.filter((job) =>
      [job.account_id, job.device_id, job.intent, job.status, job.error_message]
        .map((value) => String(value || '').toLowerCase())
        .some((value) => value.includes(term))
    )
  }, [jobs, search])

  const serverByDevice = useMemo(() => {
    const map = {}
    servers.forEach((s) => { map[s.device_id] = s })
    return map
  }, [servers])

  async function refreshAll() {
    const [batchData, deviceData, serverData, jobData, eventData, campaignData] = await Promise.all([
      get('/batches'),
      get('/devices'),
      get('/servers'),
      get('/jobs'),
      get('/events'),
      get('/virality/campaigns'),
    ])

    setBatches(batchData)
    setDevices(deviceData)
    setServers(serverData)
    setJobs(jobData)
    setEvents(eventData)
    setCampaigns(campaignData)

    if (!selectedBatch && batchData.length) {
      setSelectedBatch(String(batchData[0].id))
    }
    if (!selectedDevice && deviceData.length) {
      setSelectedDevice(String(deviceData[0].device_id || ''))
    }
  }

  useEffect(() => {
    refreshAll().catch((error) => {
      setNotice(`Initial load failed: ${error.message}`)
    })
  }, [])

  useEffect(() => {
    if (!autoRefresh) {
      return undefined
    }

    const id = setInterval(() => {
      refreshAll().catch(() => {
        // Keep polling silent to avoid repetitive error noise.
      })
    }, 7000)

    return () => clearInterval(id)
  }, [autoRefresh])

  async function runAction(label, fn) {
    setLoading(true)
    setNotice('')
    try {
      const result = await fn()
      await refreshAll()
      setNotice(`${label}: ${JSON.stringify(result)}`)
    } catch (error) {
      setNotice(`${label} failed: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  function getProposedPort(deviceId) {
    const idx = onlineDevices.indexOf(deviceId)
    return idx >= 0 ? Number(basePort) + idx : Number(basePort)
  }

  function toggleDeviceSelection(deviceId) {
    setSelectedDeviceIds((prev) =>
      prev.includes(deviceId) ? prev.filter((id) => id !== deviceId) : [...prev, deviceId]
    )
  }

  function toggleAllDevices() {
    setSelectedDeviceIds((prev) =>
      prev.length === devices.length ? [] : devices.map((d) => d.device_id)
    )
  }

  async function startSelectedServers() {
    const targets = selectedDeviceIds.filter((id) => onlineDevices.includes(id))
    if (!targets.length) {
      setNotice('No online devices selected — only online devices can start a server.')
      return
    }
    setLoading(true)
    setNotice('')
    const results = []
    for (const deviceId of targets) {
      try {
        const port = getProposedPort(deviceId)
        await postForm('/servers/start', { device_id: deviceId, server_host: serverHost, port: String(port) })
        results.push(`${deviceId}: started on :${port}`)
      } catch (e) {
        results.push(`${deviceId}: FAILED — ${e.message}`)
      }
    }
    await refreshAll()
    setNotice(results.join(' | '))
    setLoading(false)
  }

  async function stopSelectedServers() {
    if (!selectedDeviceIds.length) {
      setNotice('No devices selected.')
      return
    }
    setLoading(true)
    setNotice('')
    const results = []
    for (const deviceId of selectedDeviceIds) {
      try {
        await postForm('/servers/stop', { device_id: deviceId })
        results.push(`${deviceId}: stopped`)
      } catch (e) {
        results.push(`${deviceId}: FAILED — ${e.message}`)
      }
    }
    await refreshAll()
    setNotice(results.join(' | '))
    setLoading(false)
  }

  function renderImportTab() {
    return (
      <section className="panel">
        <SectionTitle
          title="Import Jobs"
          subtitle="Upload an Excel sheet to create a new batch."
        />
        <div className="form-grid form-grid-2">
          <div className="field">
            <label>Jobs File (.xlsx)</label>
            <input
              type="file"
              accept=".xlsx"
              onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
            />
          </div>
          <div className="field align-end">
            <button
              className="btn-primary"
              disabled={!uploadFile || loading}
              onClick={() => runAction('Import', () => postFile('/batches/import', uploadFile))}
            >
              Import File
            </button>
          </div>
        </div>
      </section>
    )
  }

  function renderWorkflowTab() {
    return (
      <section className="panel">
        <SectionTitle
          title="Batch Workflow"
          subtitle="Select batch, validate assignments, plan steps, run execution, and generate report."
        />

        <div className="form-grid form-grid-2">
          <div className="field">
            <label>Select Batch</label>
            <select value={selectedBatch} onChange={(e) => setSelectedBatch(e.target.value)}>
              <option value="">Select batch</option>
              {batches.map((batch) => (
                <option key={batch.id} value={batch.id}>
                  {batch.id} | {batch.source_file}
                </option>
              ))}
            </select>
          </div>
          <label className="toggle field-inline">
            <input type="checkbox" checked={liveMode} onChange={(e) => setLiveMode(e.target.checked)} />
            Live Appium mode
          </label>
        </div>

        <div className="action-grid">
          <button
            disabled={!selectedBatchId || loading}
            onClick={() => runAction('Validate', () => postForm(`/batches/${selectedBatchId}/validate`))}
          >
            Validate Assignment
          </button>
          <button
            disabled={!selectedBatchId || loading}
            onClick={() => runAction('Plan', () => postForm(`/batches/${selectedBatchId}/plan`))}
          >
            Plan Steps
          </button>
          <button
            className="btn-primary"
            disabled={!selectedBatchId || loading}
            onClick={() =>
              runAction('Run', () => postForm(`/batches/${selectedBatchId}/run`, { live_mode: String(liveMode) }))
            }
          >
            Run Batch
          </button>
          <button
            disabled={!selectedBatchId || loading}
            onClick={() => runAction('Report', () => postForm(`/batches/${selectedBatchId}/report`))}
          >
            Generate Report
          </button>
        </div>
      </section>
    )
  }

  function renderDevicesTab() {
    const allSelected = devices.length > 0 && selectedDeviceIds.length === devices.length
    const someSelected = selectedDeviceIds.length > 0 && selectedDeviceIds.length < devices.length

    return (
      <section className="panel">
        <SectionTitle
          title="Devices & Servers"
          subtitle="Sync ADB devices, then start or stop Appium servers. Select multiple devices for bulk actions — each device gets a unique port starting from Base Port."
        />

        {/* Config row */}
        <div className="form-grid">
          <div className="field">
            <label>Server Host</label>
            <input value={serverHost} onChange={(e) => setServerHost(e.target.value)} />
          </div>
          <div className="field">
            <label>Base Port</label>
            <input
              type="number"
              value={basePort}
              min={1024}
              max={65535}
              onChange={(e) => setBasePort(Number(e.target.value))}
            />
          </div>
          <div className="field align-end">
            <button
              disabled={loading}
              onClick={() =>
                runAction('Refresh Devices', () =>
                  postForm('/devices/sync', { server_host: serverHost, base_port: String(basePort) })
                )
              }
            >
              Refresh Devices
            </button>
          </div>
        </div>

        {/* Bulk action bar */}
        <div className="bulk-bar">
          <span className="muted-text">
            {selectedDeviceIds.length > 0
              ? `${selectedDeviceIds.length} device${selectedDeviceIds.length > 1 ? 's' : ''} selected`
              : 'Select devices below to run bulk actions'}
          </span>
          <div className="bulk-actions">
            <button
              className="btn-primary"
              disabled={selectedDeviceIds.length === 0 || loading}
              onClick={startSelectedServers}
            >
              Start Selected Servers
            </button>
            <button
              className="btn-danger"
              disabled={selectedDeviceIds.length === 0 || loading}
              onClick={stopSelectedServers}
            >
              Stop Selected Servers
            </button>
          </div>
        </div>

        {/* Device table */}
        {devices.length === 0 ? (
          <div className="empty-box">No devices found. Click "Refresh Devices" to sync via ADB.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      style={{ width: 'auto', minHeight: 'auto', padding: 0 }}
                      checked={allSelected}
                      ref={(el) => { if (el) el.indeterminate = someSelected }}
                      onChange={toggleAllDevices}
                      title="Select all devices"
                    />
                  </th>
                  <th>Device ID</th>
                  <th>Model</th>
                  <th>Platform</th>
                  <th>OS</th>
                  <th>Device Status</th>
                  <th>Assigned Port</th>
                  <th>Server Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((device) => {
                  const srv = serverByDevice[device.device_id]
                  const isOnline = device.status === 'online'
                  const port = getProposedPort(device.device_id)
                  const isChecked = selectedDeviceIds.includes(device.device_id)
                  return (
                    <tr key={device.device_id} className={isChecked ? 'row-selected' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          style={{ width: 'auto', minHeight: 'auto', padding: 0 }}
                          checked={isChecked}
                          onChange={() => toggleDeviceSelection(device.device_id)}
                        />
                      </td>
                      <td><code>{device.device_id}</code></td>
                      <td>{device.model || '—'}</td>
                      <td>{device.platform || '—'}</td>
                      <td>{device.os_version || '—'}</td>
                      <td>
                        <span className={`badge ${isOnline ? 'badge-ok' : 'badge-off'}`}>
                          {device.status}
                        </span>
                      </td>
                      <td>{isOnline ? port : '—'}</td>
                      <td>
                        {srv ? (
                          <span className={`badge ${srv.status === 'running' ? 'badge-ok' : 'badge-off'}`}>
                            {srv.status}{srv.port ? ` :${srv.port}` : ''}
                          </span>
                        ) : (
                          <span className="badge badge-off">not started</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            className="btn-sm btn-primary"
                            disabled={!isOnline || loading}
                            title={isOnline ? `Start server on port ${port}` : 'Device offline'}
                            onClick={() =>
                              runAction(`Start ${device.device_id}`, () =>
                                postForm('/servers/start', {
                                  device_id: device.device_id,
                                  server_host: serverHost,
                                  port: String(port)
                                })
                              )
                            }
                          >
                            Start
                          </button>
                          <button
                            className="btn-sm btn-danger"
                            disabled={loading || !srv}
                            title={srv ? `Stop server for ${device.device_id}` : 'No server running'}
                            onClick={() =>
                              runAction(`Stop ${device.device_id}`, () =>
                                postForm('/servers/stop', { device_id: device.device_id })
                              )
                            }
                          >
                            Stop
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    )
  }

  function renderMonitorTab() {
    return (
      <section className="panel">
        <SectionTitle
          title="Monitoring"
          subtitle="Track jobs, events, and managed servers from one place."
        />

        <div className="tab-row">
          <button
            className={activeMonitorView === 'jobs' ? 'tab active' : 'tab'}
            onClick={() => setActiveMonitorView('jobs')}
          >
            Jobs
          </button>
          <button
            className={activeMonitorView === 'events' ? 'tab active' : 'tab'}
            onClick={() => setActiveMonitorView('events')}
          >
            Run Events
          </button>
          <button
            className={activeMonitorView === 'servers' ? 'tab active' : 'tab'}
            onClick={() => setActiveMonitorView('servers')}
          >
            Servers
          </button>
          <div className="spacer" />
          {activeMonitorView === 'jobs' ? (
            <input
              className="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search jobs by account, device, intent, status..."
            />
          ) : null}
        </div>

        {activeMonitorView === 'jobs' ? (
          <DataTable
            columns={[
              'id',
              'batch_id',
              'account_id',
              'device_id',
              'intent',
              'status',
              'priority',
              'error_message',
              'evidence_path',
              'created_at'
            ]}
            rows={filteredJobs}
            emptyLabel="No jobs imported yet."
          />
        ) : null}

        {activeMonitorView === 'events' ? (
          <DataTable
            columns={['id', 'job_id', 'level', 'message', 'created_at']}
            rows={events}
            emptyLabel="No run events yet."
          />
        ) : null}

        {activeMonitorView === 'servers' ? (
          <DataTable
            columns={['device_id', 'host', 'port', 'pid', 'status', 'alive', 'started_at', 'stopped_at']}
            rows={servers}
            emptyLabel="No managed Appium servers yet."
          />
        ) : null}
      </section>
    )
  }

  function vMixTotal() {
    return Object.values(vActionMix).reduce((s, v) => s + Number(v), 0)
  }

  function renderViralityTab() {
    const accountLines = vAccounts.trim().split('\n').filter(Boolean)
    const parsedAccounts = accountLines.map((line) => {
      const [device_id, account_id] = line.split('|').map((s) => s.trim())
      return { device_id: device_id || '', account_id: account_id || '' }
    }).filter((a) => a.device_id && a.account_id)

    const mixTotal = vMixTotal()
    const mixValid = mixTotal === 100

    async function handleCreateCampaign() {
      if (!vCampaignName || !vTargetUrl || !parsedAccounts.length) {
        setNotice('Campaign name, target URL, and at least one account are required.')
        return
      }
      if (!mixValid) {
        setNotice(`Action mix must total 100% (currently ${mixTotal}%).`)
        return
      }
      await runAction('Create Campaign', () =>
        postJson('/virality/campaigns', {
          name: vCampaignName,
          target_url: vTargetUrl,
          accounts: parsedAccounts,
          wave_count: Number(vWaveCount),
          wave_gap_seconds: Number(vWaveGap),
          action_mix: Object.fromEntries(
            Object.entries(vActionMix).map(([k, v]) => [k, Number(v)])
          ),
          comment_bank: vCommentBank.split('\n').map((s) => s.trim()).filter(Boolean),
        })
      )
    }

    async function handleLoadProgress() {
      if (!selectedCampaign) return
      try {
        const data = await get(`/virality/campaigns/${selectedCampaign}/progress`)
        setCampaignProgress(data)
      } catch (e) {
        setNotice(`Progress load failed: ${e.message}`)
      }
    }

    return (
      <section className="panel">
        <SectionTitle
          title="Virality Campaigns"
          subtitle="Coordinate multi-account wave execution to spike engagement velocity and trigger the Instagram algorithm."
        />

        {/* Campaign builder */}
        <div className="virality-grid">
          {/* Left — Config */}
          <div className="virality-config">
            <h3 className="sub-heading">Campaign Setup</h3>

            <div className="form-grid form-grid-2">
              <div className="field">
                <label>Campaign Name</label>
                <input value={vCampaignName} onChange={(e) => setVCampaignName(e.target.value)} placeholder="e.g. Product Launch Wave" />
              </div>
              <div className="field">
                <label>Target Post / Reel URL</label>
                <input value={vTargetUrl} onChange={(e) => setVTargetUrl(e.target.value)} placeholder="https://www.instagram.com/p/..." />
              </div>
            </div>

            <div className="form-grid form-grid-2" style={{ marginTop: 10 }}>
              <div className="field">
                <label>Wave Count</label>
                <input type="number" min={1} max={20} value={vWaveCount} onChange={(e) => setVWaveCount(e.target.value)} />
              </div>
              <div className="field">
                <label>Wave Gap (seconds)</label>
                <input type="number" min={0} value={vWaveGap} onChange={(e) => setVWaveGap(e.target.value)} />
              </div>
            </div>

            {/* Action mix */}
            <h3 className="sub-heading" style={{ marginTop: 14 }}>Action Mix <span className={`mix-total ${mixValid ? 'mix-ok' : 'mix-warn'}`}>{mixTotal}%</span></h3>
            <div className="mix-grid">
              {Object.entries(vActionMix).map(([action, pct]) => (
                <div key={action} className="mix-row">
                  <span className="mix-label">{action}</span>
                  <input
                    type="range" min={0} max={100} value={pct}
                    onChange={(e) => setVActionMix((prev) => ({ ...prev, [action]: Number(e.target.value) }))}
                  />
                  <span className="mix-pct">{pct}%</span>
                </div>
              ))}
            </div>

            <div className="field" style={{ marginTop: 10 }}>
              <label>Comment Bank (one per line)</label>
              <textarea
                rows={4}
                value={vCommentBank}
                onChange={(e) => setVCommentBank(e.target.value)}
                placeholder="Amazing! 🔥\nLove this! ❤️"
              />
            </div>

            <label className="toggle" style={{ marginTop: 10 }}>
              <input type="checkbox" checked={vLiveMode} onChange={(e) => setVLiveMode(e.target.checked)} />
              Live Appium mode (uncheck = mock)
            </label>
          </div>

          {/* Right — Account list */}
          <div className="virality-accounts">
            <h3 className="sub-heading">Account List <span className="muted-text">({parsedAccounts.length} loaded)</span></h3>
            <p className="hint-text">Paste one account per line in format:<br /><code>device_id | account_id</code></p>
            <textarea
              className="account-textarea"
              rows={14}
              value={vAccounts}
              onChange={(e) => setVAccounts(e.target.value)}
              placeholder={`emulator-5554 | @user1\nemulator-5556 | @user2\nemulator-5558 | @user3`}
            />

            {/* Wave preview */}
            {parsedAccounts.length > 0 ? (
              <div className="wave-preview">
                <strong>Wave Distribution Preview</strong>
                {Array.from({ length: Number(vWaveCount) }, (_, i) => {
                  const count = Math.ceil((parsedAccounts.length - i) / Number(vWaveCount))
                  return (
                    <div key={i} className="wave-row">
                      <span className="wave-badge">Wave {i + 1}</span>
                      <span>{count > 0 ? count : 0} accounts</span>
                      {i > 0 ? <span className="muted-text">+{vWaveGap}s gap</span> : <span className="muted-text">immediate</span>}
                    </div>
                  )
                })}
              </div>
            ) : null}
          </div>
        </div>

        <div className="action-grid" style={{ marginTop: 14 }}>
          <button
            className="btn-primary"
            disabled={loading || !vCampaignName || !vTargetUrl || parsedAccounts.length === 0 || !mixValid}
            onClick={handleCreateCampaign}
          >
            Create Campaign
          </button>
          <button
            disabled={loading || !selectedCampaign}
            className="btn-primary"
            onClick={() =>
              runAction('Launch', () =>
                postForm(`/virality/campaigns/${selectedCampaign}/launch`, {
                  live_mode: String(vLiveMode),
                })
              )
            }
          >
            Launch Selected
          </button>
          <button disabled={loading || !selectedCampaign} onClick={handleLoadProgress}>
            View Progress
          </button>
        </div>

        {/* Campaign list */}
        <h3 className="sub-heading" style={{ marginTop: 18 }}>All Campaigns</h3>
        {campaigns.length === 0 ? (
          <div className="empty-box">No virality campaigns yet. Create one above.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Select</th>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Target URL</th>
                  <th>Accounts</th>
                  <th>Waves</th>
                  <th>Gap (s)</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id} className={String(selectedCampaign) === String(c.id) ? 'row-selected' : ''}>
                    <td>
                      <input
                        type="radio"
                        style={{ width: 'auto', minHeight: 'auto', padding: 0 }}
                        checked={String(selectedCampaign) === String(c.id)}
                        onChange={() => setSelectedCampaign(String(c.id))}
                      />
                    </td>
                    <td>{c.id}</td>
                    <td><strong>{c.name}</strong></td>
                    <td><a href={c.target_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.8rem' }}>{c.target_url.slice(0, 50)}…</a></td>
                    <td>{c.total_accounts}</td>
                    <td>{c.wave_count}</td>
                    <td>{c.wave_gap_seconds}</td>
                    <td><span className={`badge ${c.status === 'done' ? 'badge-ok' : c.status === 'running' ? 'badge-run' : 'badge-off'}`}>{c.status}</span></td>
                    <td style={{ fontSize: '0.8rem' }}>{c.created_at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Progress detail */}
        {campaignProgress ? (
          <div style={{ marginTop: 16 }}>
            <h3 className="sub-heading">
              Progress — {campaignProgress.campaign?.name}
              <span className={`badge ${campaignProgress.campaign?.status === 'done' ? 'badge-ok' : 'badge-run'}`} style={{ marginLeft: 8 }}>
                {campaignProgress.campaign?.status}
              </span>
            </h3>
            <div className="form-grid" style={{ gap: 8, marginBottom: 10 }}>
              {Object.entries(campaignProgress.summary || {}).map(([status, count]) => (
                <StatCard key={status} label={status} value={count} />
              ))}
            </div>
            <DataTable
              columns={['wave_number', 'action', 'status', 'count']}
              rows={campaignProgress.wave_breakdown || []}
              emptyLabel="No wave data yet."
            />
          </div>
        ) : null}
      </section>
    )
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <h1>Automation Platform</h1>
          <p>Clean tab-based workspace for import, execution workflow, device management, and monitoring.</p>
        </div>
        <div className="hero-actions">
          <label className="toggle">
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
            Auto-refresh
          </label>
          <button disabled={loading} onClick={() => runAction('Refresh', refreshAll)}>
            Refresh Now
          </button>
        </div>
      </header>

      {notice && <div className="notice">{notice}</div>}

      <section className="stats-grid">
        <StatCard label="Batches" value={batches.length} />
        <StatCard label="Devices" value={devices.length} />
        <StatCard label="Online Devices" value={onlineDevices.length} />
        <StatCard label="Managed Servers" value={servers.length} />
        <StatCard label="Campaigns" value={campaigns.length} />
      </section>

      <section className="panel top-tabs-panel">
        <div className="tab-row">
          <button className={activeView === 'import' ? 'tab active' : 'tab'} onClick={() => setActiveView('import')}>
            Import
          </button>
          <button className={activeView === 'workflow' ? 'tab active' : 'tab'} onClick={() => setActiveView('workflow')}>
            Batch Workflow
          </button>
          <button className={activeView === 'devices' ? 'tab active' : 'tab'} onClick={() => setActiveView('devices')}>
            Devices & Servers
          </button>
          <button className={activeView === 'monitor' ? 'tab active' : 'tab'} onClick={() => setActiveView('monitor')}>
            Monitoring
          </button>
          <button className={activeView === 'virality' ? 'tab active tab-virality' : 'tab tab-virality'} onClick={() => setActiveView('virality')}>
            🔥 Virality
          </button>
          <div className="spacer" />
          <div className="status-inline">
            <span>Batch: {selectedBatch || 'None'}</span>
            <span>Device: {selectedDevice || 'None'}</span>
            <span>Mode: {liveMode ? 'Live' : 'Mock'}</span>
          </div>
        </div>
      </section>

      {activeView === 'import' ? renderImportTab() : null}
      {activeView === 'workflow' ? renderWorkflowTab() : null}
      {activeView === 'devices' ? renderDevicesTab() : null}
      {activeView === 'monitor' ? renderMonitorTab() : null}
      {activeView === 'virality' ? renderViralityTab() : null}
    </div>
  )
}
