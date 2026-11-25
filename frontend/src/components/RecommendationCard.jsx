import { DataRow } from './ui';
import { statusInfo } from '../utils/bpStatus';

/** One piece of advice. The colour bar follows the blood-pressure band it was written for. */
export default function RecommendationCard({ rec }) {
  return (
    <DataRow align="start" accent={rec.based_on_trend ? statusInfo(rec.based_on_trend).accent : '#94A3B8'}>
      <div className="hs-body-text">{rec.message}</div>
    </DataRow>
  );
}
