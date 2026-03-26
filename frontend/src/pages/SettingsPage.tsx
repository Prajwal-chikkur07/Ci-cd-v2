import { useState } from 'react';
import { User, Bell, Shield, Key, Cloud, Eye, EyeOff, Plus, Trash2, CheckCircle } from 'lucide-react';

type Section = 'profile' | 'notifications' | 'security' | 'apikeys' | 'cloud';

const sections: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'profile',       label: 'Profile',            icon: <User className="w-4 h-4" /> },
  { id: 'notifications', label: 'Notifications',      icon: <Bell className="w-4 h-4" /> },
  { id: 'security',      label: 'Security',           icon: <Shield className="w-4 h-4" /> },
  { id: 'apikeys',       label: 'API Keys',           icon: <Key className="w-4 h-4" /> },
  { id: 'cloud',         label: 'Cloud Integrations', icon: <Cloud className="w-4 h-4" /> },
];

const inputCls = "w-full px-3.5 py-2.5 bg-white border border-[#e5e7eb] rounded-lg text-sm text-[#111827] placeholder-[#9ca3af] focus:ring-2 focus:ring-[#111827]/10 focus:border-[#111827] outline-none transition-all";

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} className="relative flex-shrink-0">
      <div className={`w-10 h-5 rounded-full transition-colors ${checked ? 'bg-[#111827]' : 'bg-[#e5e7eb]'}`} />
      <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-5' : ''}`} />
    </button>
  );
}

function Card({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-[#e5e7eb] rounded-xl shadow-card mb-4 overflow-hidden">
      <div className="px-6 py-4 border-b border-[#f3f4f6]">
        <h3 className="text-sm font-semibold text-[#111827]">{title}</h3>
        {desc && <p className="text-xs text-[#6b7280] mt-0.5">{desc}</p>}
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [section, setSection] = useState<Section>('profile');
  const [saved, setSaved] = useState(false);
  const [name, setName] = useState('Prajwal Chikkur');
  const [email, setEmail] = useState('pchikkur@example.com');
  const [notifs, setNotifs] = useState({ success: true, failure: true, security: true, weekly: false });
  const [twoFA, setTwoFA] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [currentPass, setCurrentPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [keys, setKeys] = useState([
    { id: '1', name: 'Production Key', key: 'sk-prod-••••••••••••••••', created: '2026-01-15' },
    { id: '2', name: 'CI/CD Key',      key: 'sk-cicd-••••••••••••••••', created: '2026-02-20' },
  ]);
  const [clouds, setClouds] = useState({ aws: false, gcp: false, azure: false });

  const handleSave = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };

  return (
    <div className="flex-1 overflow-hidden flex flex-col bg-[#f9fafb]">
      {/* Header */}
      <div className="bg-white border-b border-[#e5e7eb] px-8 pt-7 pb-5 flex-shrink-0">
        <h1 className="text-2xl font-bold text-[#111827]">Settings</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">Manage your account and preferences</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-[200px] border-r border-[#e5e7eb] bg-white p-4 flex-shrink-0">
          <nav className="space-y-0.5">
            {sections.map(s => (
              <button key={s.id} onClick={() => setSection(s.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                  section === s.id ? 'bg-[#f3f4f6] text-[#111827] font-medium' : 'text-[#6b7280] hover:bg-[#f9fafb] hover:text-[#111827]'
                }`}>
                {s.icon}{s.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          {section === 'profile' && (
            <>
              <Card title="Personal Information" desc="Update your name and email address">
                <div className="space-y-4 max-w-md">
                  <div>
                    <label className="block text-xs font-medium text-[#374151] mb-1.5">Full Name</label>
                    <input value={name} onChange={e => setName(e.target.value)} className={inputCls} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[#374151] mb-1.5">Email Address</label>
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)} className={inputCls} />
                  </div>
                </div>
              </Card>
              <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-[#111827] hover:bg-[#1f2937] text-white text-sm font-medium rounded-lg transition-colors">
                {saved ? <><CheckCircle className="w-4 h-4" />Saved!</> : 'Save Changes'}
              </button>
            </>
          )}

          {section === 'notifications' && (
            <Card title="Notification Preferences" desc="Choose when you want to be notified">
              <div className="space-y-0 divide-y divide-[#f3f4f6]">
                {[
                  { key: 'success' as const, label: 'Pipeline Success', desc: 'Get notified when a pipeline completes successfully' },
                  { key: 'failure' as const, label: 'Pipeline Failure', desc: 'Get notified when a pipeline fails' },
                  { key: 'security' as const, label: 'Security Issues', desc: 'Alerts for security vulnerabilities detected' },
                  { key: 'weekly' as const, label: 'Weekly Summary', desc: 'Weekly digest of pipeline activity' },
                ].map(({ key, label, desc }) => (
                  <div key={key} className="flex items-center justify-between py-4">
                    <div>
                      <div className="text-sm font-medium text-[#111827]">{label}</div>
                      <div className="text-xs text-[#6b7280] mt-0.5">{desc}</div>
                    </div>
                    <Toggle checked={notifs[key]} onChange={v => setNotifs(prev => ({ ...prev, [key]: v }))} />
                  </div>
                ))}
              </div>
            </Card>
          )}

          {section === 'security' && (
            <>
              <Card title="Two-Factor Authentication" desc="Add an extra layer of security">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-[#111827]">Enable 2FA</div>
                    <div className="text-xs text-[#6b7280] mt-0.5">Protect your account with an authenticator app</div>
                  </div>
                  <Toggle checked={twoFA} onChange={setTwoFA} />
                </div>
              </Card>
              <Card title="Change Password" desc="Update your account password">
                <div className="space-y-4 max-w-md">
                  <div className="relative">
                    <label className="block text-xs font-medium text-[#374151] mb-1.5">Current Password</label>
                    <input type={showPass ? 'text' : 'password'} value={currentPass} onChange={e => setCurrentPass(e.target.value)} className={`${inputCls} pr-10`} />
                    <button onClick={() => setShowPass(v => !v)} className="absolute right-3 top-8 text-[#9ca3af] hover:text-[#6b7280]">
                      {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[#374151] mb-1.5">New Password</label>
                    <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} className={inputCls} />
                  </div>
                  <button onClick={handleSave} className="px-4 py-2 bg-[#111827] hover:bg-[#1f2937] text-white text-sm font-medium rounded-lg transition-colors">
                    {saved ? 'Updated!' : 'Update Password'}
                  </button>
                </div>
              </Card>
            </>
          )}

          {section === 'apikeys' && (
            <Card title="API Keys" desc="Manage your API keys for programmatic access">
              <div className="space-y-3 mb-4">
                {keys.map(k => (
                  <div key={k.id} className="flex items-center gap-3 p-3.5 bg-[#f9fafb] rounded-lg border border-[#e5e7eb]">
                    <Key className="w-4 h-4 text-[#9ca3af] flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-[#111827]">{k.name}</div>
                      <div className="text-xs font-mono text-[#9ca3af] mt-0.5">{k.key}</div>
                    </div>
                    <span className="text-xs text-[#9ca3af]">{k.created}</span>
                    <button onClick={() => setKeys(prev => prev.filter(x => x.id !== k.id))}
                      className="p-1.5 hover:bg-[#fef2f2] rounded-lg transition-colors">
                      <Trash2 className="w-3.5 h-3.5 text-[#ef4444]" />
                    </button>
                  </div>
                ))}
              </div>
              <button onClick={() => setKeys(prev => [...prev, { id: Date.now().toString(), name: 'New Key', key: `sk-${Math.random().toString(36).slice(2, 18)}`, created: new Date().toISOString().slice(0, 10) }])}
                className="flex items-center gap-2 px-4 py-2 bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#e5e7eb] text-sm text-[#374151] font-medium rounded-lg transition-colors">
                <Plus className="w-4 h-4" />Generate New Key
              </button>
            </Card>
          )}

          {section === 'cloud' && (
            <Card title="Cloud Integrations" desc="Connect your cloud providers for deployments">
              <div className="space-y-3">
                {[
                  { key: 'aws' as const, label: 'Amazon Web Services', desc: 'Deploy to ECS, Lambda, or EC2', logo: '🟠' },
                  { key: 'gcp' as const, label: 'Google Cloud Platform', desc: 'Deploy to Cloud Run, GKE, or App Engine', logo: '🔵' },
                  { key: 'azure' as const, label: 'Microsoft Azure', desc: 'Deploy to Azure Container Apps or AKS', logo: '🔷' },
                ].map(({ key, label, desc, logo }) => (
                  <div key={key} className="flex items-center justify-between p-4 bg-[#f9fafb] rounded-lg border border-[#e5e7eb]">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{logo}</span>
                      <div>
                        <div className="text-sm font-medium text-[#111827]">{label}</div>
                        <div className="text-xs text-[#6b7280] mt-0.5">{desc}</div>
                      </div>
                    </div>
                    <button onClick={() => setClouds(prev => ({ ...prev, [key]: !prev[key] }))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                        clouds[key]
                          ? 'bg-[#f0fdf4] text-[#16a34a] border-[#bbf7d0]'
                          : 'bg-white text-[#374151] border-[#e5e7eb] hover:bg-[#f3f4f6]'
                      }`}>
                      {clouds[key] ? 'Connected' : 'Connect'}
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
