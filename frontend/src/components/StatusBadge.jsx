const LABELS = {
    controlled:'Controlled',
    elevated:'Elevated',
    high:'High',
    low:'Low',
    no_data:'No Data',
};
export default function StatusBadge({status}) {
    const className = `hs-status-badge hs-status-${status}`;
    return <span className={className}>{LABELS[status] || status}</span>;
}