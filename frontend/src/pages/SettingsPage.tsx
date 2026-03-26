import { useState } from 'react';
import { User, Bell, Shield, Key, Cloud, Eye, EyeOff, Plus, Trash2, CheckCircle } from 'lucide-react';

type Section = 'profile' | 'notifications' | 'security' | 'apikeys' | 'cloud';

const sections: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'profile',       label: 'Profile',         icon: <User className="w-4 h-4" /> },
  { id: 'notifications', label: 'Notifications',   icon: <Bell className="w-4 h-4" /> },
  { id: 'security',      label: 'Security',        icon: <Shield className="w-4 h-4" /> },
  { id: 'apikeys',       label: 'API Keys',        icon: <Key className="w-4 h-4" /> },
  { id: 'cloud',         label: 'Cloud Integrations', icon: <Cloud className="w-4 h-4" /> },
];

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} className="relative flex-shrink-0">
      <div className={`w-10 h-5 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-[#374151]'}`} />
      <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-5' : ''}`} />
    </button>
  );
}

function Input({ label, value, onChange, type = 'text', placeholder = '' }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <div>
      <label className="block text-sm text-[#9ca3af] mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3.5 py-2.5 bg-[#1f2937] border border-[#374151] rounded-lg text-sm text-white placeholder-[#4b5563] focus:ring-1 focus:ring-accent focus:border-accent outline-none transition-all"
      />
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-4">
      <h3 className="text-sm font-semibold text-white mb-4">{title}</h3>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const [section, setSection] = useState<Section>('profile');
  const [saved, setSaved] = useState(false);

  // Profile
  const [name, setName] = useState('Prajwal Chikkur');
  const [email, setEmail] = useState('pchikkur@example.com');

  // Notifications
  const [notifs, setNotifs] = useState({ success: true, failure: true, security: true, weekly: false });

  // Security
  const [twoFA, setTwoFA] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [currentPass, setCurrentPass] = useState('');
  const [newPass, setNewPass] = useState('');

  // API Keys
  const [keys, setKeys] = useState([
    { id: '1', name: 'Production Key', key: 'sk-prod-••••••••••••••••', created: '2026-01-15' },
    { id: '2', name: 'CI/CD Key', key: 'sk-cicd-••••••••••••••••', created: '2026-02-20' },
  ]);

  // Cloud
  const [clouds, setClouds] = useState({ aws: false, gcp: false, azure: false });

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const generateKey = () => {
    const newKey = { id: Date.now().toString(), name: 'New Key', key: `sk-${Math.random().toString(36).slice(2, 18)}`, created: new Date().toISOString().slice(0, 10) };
    setKeys(prev => [...prev, newKey]);
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar */}
      <aside className="w-[200px] border-r border-[#1f2937] p-4 flex-shrink-0">
        <nav className="space-y-0.5">
          {sections.map(s => (
            <button key={s.id} onClick={() => setSection(s.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                section === s.id ? 'bg-accent/10 text-accent' : 'text-[#6b7280] hover:bg-[#1f2937] hover:text-white'
              }`}>
              {s.icon}{s.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {section === 'profile' && (
          <>
            <Card title="Personal Information">
              <div className="space-y-4">
                <Input label="Full Name" value={name} onChange={setName} placeholder="Your name" />
                <Input label="Email Address" value={email} onChange={setEmail} type="email" placeholder="you@example.com" />
              </div>
            </Card>
            <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors">
              {saved ? <><CheckCircle className="w-4 h-4" />Saved!</> : 'Save Changes'}
            </button>
          </>
        )}

        {section === 'notifications' && (
          <Card title="Notification Preferences">
            <div className="space-y-4">
              {[
                { key: 'success' as const, label: 'Pipeline Success', desc: 'Get notified when a pipeline completes successfully' },
                { key: 'failure' as const, label: 'Pipeline Failure', desc: 'Get notified when a pipeline fails' },
                { key: 'security' as const, label: 'Security Issues', desc: 'Alerts for security vulnerabilities detected' },
                { key: 'weekly' as const, label: 'Weekly Summary', desc: 'Weekly digest of pipeline activity' },
              ].map(({ key, label, desc }) => (
                <div key={key} className="flex items-center justify-between py-3 border-b border-[#1f2937] last:border-0">
                  <div>
                    <div className="text-sm text-white">{label}</div>
                    <div className="text-xs text-[#4b5563] mt-0.5">{desc}</div>
                  </div>
                  <Toggle checked={notifs[key]} onChange={v => setNotifs(prev => ({ ...prev, [key]: v }))} />
                </div>
              ))}
            </div>
          </Card>
        )}

        {section === 'security' && (
          <>
            <Card title="Two-Factor Authentication">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-white">Enable 2FA</div>
                  <div className="text-xs text-[#4b5563] mt-0.5">Add an extra layer of security to your account</div>
                </div>
                <Toggle checked={twoFA} onChange={setTwoFA} />
              </div>
            </Card>
            <Card title="Change Password">
              <div className="space-y-4">
                <div className="relative">
                  <label className="block text-sm text-[#9ca3af] mb-1.5">Current Password</label>
                  <input type={showPass ? 'text' : 'password'} value={currentPass} onChange={e => setCurrentPass(e.target.value)}
                    className="w-full px-3.5 py-2.5 pr-10 bg-[#1f2937] border border-[#374151] rounded-lg text-sm text-white outline-none focus:ring-1 focus:ring-accent focus:border-accent" />
                  <button onClick={() => setShowPass(v => !v)} className="absolute right-3 top-9 text-[#4b5563]">
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <Input label="New Password" value={newPass} onChange={setNewPass} type="password" />
                <button onClick={handleSave} className="px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors">
                  {saved ? 'Updated!' : 'Update Password'}
                </button>
              </div>
            </Card>
          </>
        )}

        {section === 'apikeys' && (
          <Card title="API Keys">
            <div className="space-y-3 mb-4">
              {keys.map(k => (
                <div key={k.id} className="flex items-center gap-3 p-3 bg-[#1f2937] rounded-lg border border-[#374151]">
                  <Key className="w-4 h-4 text-[#4b5563] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white">{k.name}</div>
                    <div className="text-xs font-mono text-[#4b5563] mt-0.5">{k.key}</div>
                  </div>
                  <span className="text-xs text-[#374151]">{k.created}</span>
                  <button onClick={() => setKeys(prev => prev.filter(x => x.id !== k.id))}
                    className="p-1.5 hover:bg-red-900/30 rounded-md transition-colors">
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </div>
              ))}
            </div>
            <button onClick={generateKey} className="flex items-center gap-2 px-4 py-2 bg-[#1f2937] hover:bg-[#374151] border border-[#374151] text-sm text-[#9ca3af] rounded-lg transition-colors">
              <Plus className="w-4 h-4" />Generate New Key
            </button>
          </Card>
        )}

        {section === 'cloud' && (
          <Card title="Cloud Integrations">
            <div className="space-y-4">
              {[
                { key: 'aws' as const, label: 'Amazon Web Services', desc: 'Deploy to ECS, Lambda, or EC2', logo: '🟠' },
                { key: 'gcp' as const, label: 'Google Cloud Platform', desc: 'Deploy to Cloud Run, GKE, or App Engine', logo: '🔵' },
                { key: 'azure' as const, label: 'Microsoft Azure', desc: 'Deploy to Azure Container Apps or AKS', logo: '🔷' },
              ].map(({ key, label, desc, logo }) => (
                <div key={key} className="flex items-center justify-between p-4 bg-[#1f2937] rounded-lg border border-[#374151]">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{logo}</span>
                    <div>
                      <div className="text-sm text-white font-medium">{label}</div>
                      <div className="text-xs text-[#4b5563] mt-0.5">{desc}</div>
                    </div>
                  </div>
                  <button
                    onClick={() => setClouds(prev => ({ ...prev, [key]: !prev[key] }))}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      clouds[key] ? 'bg-accent/10 text-accent border border-accent/20' : 'bg-[#374151] text-[#9ca3af] hover:bg-[#4b5563]'
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
  );
}
