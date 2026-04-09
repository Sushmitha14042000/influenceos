import { useEffect, useMemo, useState } from 'react'
import { get, postFile, postForm } from './api'

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
    const [batchData, deviceData, serverData, jobData, eventData] = await Promise.all([
      get('/batches'),
      get('/devices'),
      get('/servers'),
      get('/jobs'),
      get('/events')
    ])

    setBatches(batchData)
    setDevices(deviceData)
    setServers(serverData)
    setJobs(jobData)
    setEvents(eventData)

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
    </div>
  )
}
