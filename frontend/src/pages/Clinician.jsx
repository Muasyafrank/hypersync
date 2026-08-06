import { useState, useEffect } from 'react';
import { Container, Row, Col, Button, Badge, Spinner, Alert, Table } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend 
} from 'recharts';
import { 
  Heart, TrendingUp, Activity, Bell, ArrowRight, 
  Users, Calendar, Clock, ChevronRight, UserCheck,
  FileText, Plus, Search, Filter
} from 'lucide-react';
import Layout from '../components/Layout';

// Dummy data for clinicians
const DUMMY_PATIENTS = [
  {
    id: 1,
    name: 'Sarah Johnson',
    age: 62,
    gender: 'Female',
    lastVisit: '2026-08-05T10:30:00',
    condition: 'Hypertension',
    status: 'elevated',
    systolic: 145,
    diastolic: 92,
    medication: 'Lisinopril 10mg',
    nextAppointment: '2026-08-20T14:00:00'
  },
  {
    id: 2,
    name: 'Robert Chen',
    age: 71,
    gender: 'Male',
    lastVisit: '2026-08-04T15:45:00',
    condition: 'Type 2 Diabetes',
    status: 'controlled',
    systolic: 132,
    diastolic: 84,
    medication: 'Metformin 500mg',
    nextAppointment: '2026-08-18T09:30:00'
  },
  {
    id: 3,
    name: 'Maria Garcia',
    age: 55,
    gender: 'Female',
    lastVisit: '2026-08-03T11:20:00',
    condition: 'Heart Disease',
    status: 'high',
    systolic: 158,
    diastolic: 96,
    medication: 'Amlodipine 5mg',
    nextAppointment: '2026-08-15T16:00:00'
  },
  {
    id: 4,
    name: 'James Wilson',
    age: 68,
    gender: 'Male',
    lastVisit: '2026-08-02T09:00:00',
    condition: 'Hypertension',
    status: 'controlled',
    systolic: 128,
    diastolic: 78,
    medication: 'Hydrochlorothiazide 25mg',
    nextAppointment: '2026-08-22T10:00:00'
  },
  {
    id: 5,
    name: 'Patricia Brown',
    age: 59,
    gender: 'Female',
    lastVisit: '2026-08-01T13:30:00',
    condition: 'Chronic Kidney Disease',
    status: 'elevated',
    systolic: 142,
    diastolic: 88,
    medication: 'Losartan 50mg',
    nextAppointment: '2026-08-25T11:30:00'
  }
];

const RECENT_ACTIVITIES = [
  { id: 1, action: 'Patient update', patient: 'Sarah Johnson', time: '10 min ago', type: 'update' },
  { id: 2, action: 'New reading added', patient: 'Robert Chen', time: '1 hour ago', type: 'reading' },
  { id: 3, action: 'Appointment scheduled', patient: 'Maria Garcia', time: '3 hours ago', type: 'appointment' },
  { id: 4, action: 'Prescription refilled', patient: 'James Wilson', time: '5 hours ago', type: 'prescription' },
  { id: 5, action: 'Lab results received', patient: 'Patricia Brown', time: '1 day ago', type: 'lab' }
];

const WEEKLY_STATS = [
  { day: 'Mon', patients: 12, readings: 34 },
  { day: 'Tue', patients: 8, readings: 28 },
  { day: 'Wed', patients: 15, readings: 42 },
  { day: 'Thu', patients: 10, readings: 31 },
  { day: 'Fri', patients: 14, readings: 38 },
  { day: 'Sat', patients: 6, readings: 19 },
  { day: 'Sun', patients: 4, readings: 12 }
];

const STATUS_DISTRIBUTION = [
  { name: 'Controlled', value: 45, color: '#10b981' },
  { name: 'Elevated', value: 30, color: '#f59e0b' },
  { name: 'High', value: 15, color: '#ef4444' },
  { name: 'Critical', value: 10, color: '#7c3aed' }
];

// Dummy statistics
const CLINIC_STATS = {
  totalPatients: 284,
  activePatients: 156,
  appointmentsToday: 18,
  pendingResults: 7,
  averageSystolic: 138,
  averageDiastolic: 84,
  controlledRate: 62
};

// Helper function for status colors
const getStatusInfo = (status) => {
  const statusMap = {
    'controlled': { label: 'Controlled', bg: '#d1fae5', color: '#065f46', border: '#10b981' },
    'elevated': { label: 'Elevated', bg: '#fef3c7', color: '#92400e', border: '#f59e0b' },
    'high': { label: 'High', bg: '#fee2e2', color: '#991b1b', border: '#ef4444' },
    'critical': { label: 'Critical', bg: '#ede9fe', color: '#5b21b6', border: '#7c3aed' },
    'normal': { label: 'Normal', bg: '#dbeafe', color: '#1e40af', border: '#3b82f6' }
  };
  return statusMap[status] || { label: 'Unknown', bg: '#e5e7eb', color: '#374151', border: '#6b7280' };
};

export default function ClinicianDashboard() {
  const navigate = useNavigate();
  
  // State with dummy data
  const [patients, setPatients] = useState(DUMMY_PATIENTS);
  const [activities, setActivities] = useState(RECENT_ACTIVITIES);
  const [weeklyData, setWeeklyData] = useState(WEEKLY_STATS);
  const [statusDistribution, setStatusDistribution] = useState(STATUS_DISTRIBUTION);
  const [stats, setStats] = useState(CLINIC_STATS);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  // Filter patients
  const filteredPatients = patients.filter(patient => {
    const matchesSearch = patient.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          patient.condition.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === 'all' || patient.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  // Quick stats cards data
  const quickStats = [
    { 
      title: 'Total Patients', 
      value: stats.totalPatients,
      subtitle: `${stats.activePatients} active`,
      icon: Users,
      color: '#3b82f6',
      bg: '#dbeafe'
    },
    { 
      title: 'Appointments Today', 
      value: stats.appointmentsToday,
      subtitle: '10:00 AM - 4:00 PM',
      icon: Calendar,
      color: '#10b981',
      bg: '#d1fae5'
    },
    { 
      title: 'Pending Results', 
      value: stats.pendingResults,
      subtitle: 'Need follow-up',
      icon: FileText,
      color: '#f59e0b',
      bg: '#fef3c7'
    },
    { 
      title: 'Avg Blood Pressure', 
      value: `${stats.averageSystolic}/${stats.averageDiastolic}`,
      subtitle: `${stats.controlledRate}% controlled`,
      icon: Heart,
      color: '#ef4444',
      bg: '#fee2e2'
    }
  ];

  return (
    <Layout>
      <Container fluid className="py-4">
        {/* Header */}
        <div className="d-flex justify-content-between align-items-center mb-4">
          <div>
            <h1 className="mb-1" style={{ color: '#0f172a', fontWeight: 700 }}>
              Clinician Dashboard
            </h1>
            <p style={{ color: '#64748b', fontSize: '0.95rem' }}>
              Real-time overview of your patients and clinic metrics
            </p>
          </div>
          <div className="d-flex gap-2">
            <Button 
              variant="outline-primary" 
              className="d-flex align-items-center gap-2"
              onClick={() => navigate('/patients')}
            >
              <Users size={18} />
              All Patients
            </Button>
            <Button 
              className="d-flex align-items-center gap-2"
              onClick={() => navigate('/patients/new')}
              style={{ backgroundColor: '#0d9488', borderColor: '#0d9488' }}
            >
              <Plus size={18} />
              Add Patient
            </Button>
          </div>
        </div>

        {/* Quick Stats */}
        <Row className="g-3 mb-4">
          {quickStats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <Col md={3} sm={6} key={index}>
                <div className="border rounded p-3 h-100" style={{ backgroundColor: 'white' }}>
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div style={{ 
                      width: '40px', 
                      height: '40px', 
                      borderRadius: '10px', 
                      backgroundColor: stat.bg,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      <Icon size={20} color={stat.color} />
                    </div>
                    <ChevronRight size={16} color="#94a3b8" />
                  </div>
                  <div className="h3 mb-1" style={{ fontWeight: 700, color: '#0f172a' }}>
                    {stat.value}
                  </div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 500, color: '#1e293b' }}>
                    {stat.title}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    {stat.subtitle}
                  </div>
                </div>
              </Col>
            );
          })}
        </Row>

        <Row className="g-3">
          {/* Patients List - Left Column */}
          <Col lg={7}>
            <div className="border rounded p-3" style={{ backgroundColor: 'white' }}>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-1" style={{ fontWeight: 600, color: '#0f172a' }}>
                    Patients
                  </h5>
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>
                    Manage your patient list
                  </p>
                </div>
                <Button 
                  variant="link" 
                  className="text-decoration-none d-flex align-items-center gap-1"
                  style={{ color: '#0d9488', fontSize: '0.9rem' }}
                  onClick={() => navigate('/patients')}
                >
                  View All <ArrowRight size={14} />
                </Button>
              </div>

              {/* Search and Filter */}
              <div className="d-flex gap-2 mb-3">
                <div className="position-relative flex-grow-1">
                  <Search size={18} className="position-absolute" style={{ 
                    left: '12px', 
                    top: '50%', 
                    transform: 'translateY(-50%)',
                    color: '#94a3b8'
                  }} />
                  <input
                    type="text"
                    placeholder="Search patients..."
                    className="form-control"
                    style={{ paddingLeft: '40px' }}
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <select 
                  className="form-select"
                  style={{ width: '150px' }}
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="all">All Status</option>
                  <option value="controlled">Controlled</option>
                  <option value="elevated">Elevated</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              {/* Patient Cards */}
              <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {filteredPatients.length === 0 ? (
                  <div className="text-center py-4" style={{ color: '#94a3b8' }}>
                    No patients found
                  </div>
                ) : (
                  filteredPatients.map((patient) => {
                    const status = getStatusInfo(patient.status);
                    return (
                      <div 
                        key={patient.id}
                        className="border rounded p-3 mb-2"
                        style={{ cursor: 'pointer', transition: 'all 0.2s' }}
                        onClick={() => navigate(`/patients/${patient.id}`)}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#f8fafc';
                          e.currentTarget.style.borderColor = '#0d9488';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'white';
                          e.currentTarget.style.borderColor = '#e5e7eb';
                        }}
                      >
                        <div className="d-flex justify-content-between align-items-start">
                          <div>
                            <div className="d-flex align-items-center gap-2">
                              <h6 className="mb-0" style={{ fontWeight: 600, color: '#0f172a' }}>
                                {patient.name}
                              </h6>
                              <Badge style={{ 
                                backgroundColor: status.bg, 
                                color: status.color,
                                padding: '0.25rem 0.6rem',
                                borderRadius: '20px',
                                fontWeight: 600
                              }}>
                                {status.label}
                              </Badge>
                            </div>
                            <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '4px' }}>
                              {patient.age} yrs • {patient.gender} • {patient.condition}
                            </div>
                            <div className="d-flex align-items-center gap-3 mt-2" style={{ fontSize: '0.85rem' }}>
                              <span style={{ color: '#64748b' }}>
                                <Heart size={14} className="me-1" />
                                {patient.systolic}/{patient.diastolic} mmHg
                              </span>
                              <span style={{ color: '#64748b' }}>
                                <Clock size={14} className="me-1" />
                                Last visit: {new Date(patient.lastVisit).toLocaleDateString()}
                              </span>
                            </div>
                          </div>
                          <div style={{ textAlign: 'right', fontSize: '0.8rem' }}>
                            <div style={{ color: '#64748b' }}>Next appointment</div>
                            <div style={{ fontWeight: 600, color: '#0f172a' }}>
                              {new Date(patient.nextAppointment).toLocaleDateString()}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                              {new Date(patient.nextAppointment).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </Col>

          {/* Right Column */}
          <Col lg={5}>
            {/* Status Distribution Chart */}
            <div className="border rounded p-3 mb-3" style={{ backgroundColor: 'white' }}>
              <h5 className="mb-1" style={{ fontWeight: 600, color: '#0f172a' }}>
                Patient Status Distribution
              </h5>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                Overall health status breakdown
              </p>
              
              <div style={{ height: '240px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statusDistribution}
                      dataKey="value"
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={4}
                    >
                      {statusDistribution.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              
              <div className="d-flex justify-content-center gap-3 mt-2">
                {statusDistribution.map((item, index) => (
                  <div className="d-flex align-items-center gap-1" key={index}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: item.color }} />
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {item.name} ({item.value}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Weekly Activity */}
            <div className="border rounded p-3 mb-3" style={{ backgroundColor: 'white' }}>
              <h5 className="mb-1" style={{ fontWeight: 600, color: '#0f172a' }}>
                Weekly Activity
              </h5>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                Patients seen and readings taken
              </p>
              
              <div style={{ height: '180px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={weeklyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <Tooltip />
                    <Bar dataKey="patients" fill="#0d9488" name="Patients" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="readings" fill="#3b82f6" name="Readings" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="border rounded p-3" style={{ backgroundColor: 'white' }}>
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h5 className="mb-0" style={{ fontWeight: 600, color: '#0f172a' }}>
                  Recent Activity
                </h5>
                <Button 
                  variant="link" 
                  className="text-decoration-none p-0"
                  style={{ color: '#0d9488', fontSize: '0.85rem' }}
                >
                  View All
                </Button>
              </div>
              {activities.map((activity) => (
                <div key={activity.id} className="d-flex align-items-center gap-3 py-2 border-bottom">
                  <div style={{ 
                    width: '32px', 
                    height: '32px', 
                    borderRadius: '50%', 
                    backgroundColor: '#f1f5f9',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    <UserCheck size={14} color="#64748b" />
                  </div>
                  <div className="flex-grow-1">
                    <div style={{ fontSize: '0.9rem', fontWeight: 500, color: '#0f172a' }}>
                      {activity.action}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                      {activity.patient}
                    </div>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                    {activity.time}
                  </div>
                </div>
              ))}
            </div>
          </Col>
        </Row>
      </Container>
    </Layout>
  );
}