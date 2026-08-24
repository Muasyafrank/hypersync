from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.core.trend_analysis import compute_trend
from app.models.environmental_factor import EnvironmentalFactor


def generate_recommendations(db: Session, patient_id, period_days: int = 7) -> list[dict]:
    trend = compute_trend(db, patient_id, period_days)
    recommendations: list[dict] = []

    if trend.status == "no_data":
        recommendations.append({
            "message": "You haven't logged any readings recently. Try to record your blood pressure at a consistent time each day for more reliable trends.",
            "based_on_trend": None,
        })
        return recommendations

    # Pull the most recent environmental factor entry within the same window
    cutoff = date.today() - timedelta(days=period_days)
    recent_factor = (
        db.query(EnvironmentalFactor)
        .filter(EnvironmentalFactor.patient_id == patient_id, EnvironmentalFactor.logged_date >= cutoff)
        .order_by(EnvironmentalFactor.logged_date.desc())
        .first()
    )

    if trend.status in ("elevated", "high"):
        recommendations.append({
            "message": (
                f"Your average blood pressure over the last {period_days} days is {trend.status}. "
                "Consider reducing salt intake, staying physically active, and monitoring more frequently."
            ),
            "based_on_trend": trend.status,
        })

        if recent_factor:
            if recent_factor.stress_level == "high":
                recommendations.append({
                    "message": "You've logged high stress recently, which can raise blood pressure. Consider relaxation techniques such as deep breathing or a short walk.",
                    "based_on_trend": trend.status,
                })
            if recent_factor.sleep_hours is not None and recent_factor.sleep_hours < 6:
                recommendations.append({
                    "message": "Your recent sleep has been under 6 hours. Poor sleep is linked to higher blood pressure — aim for 7–8 hours where possible.",
                    "based_on_trend": trend.status,
                })
            if recent_factor.medication_taken is False:
                recommendations.append({
                    "message": "You logged a missed dose of medication recently. Missing doses can contribute to elevated readings — consider setting a daily reminder.",
                    "based_on_trend": trend.status,
                })
            if recent_factor.diet_adherence is False:
                recommendations.append({
                    "message": "You logged not following your recommended diet recently. Dietary adherence plays a significant role in blood pressure control.",
                    "based_on_trend": trend.status,
                })
        else:
            recommendations.append({
                "message": "Log your stress, sleep, diet, and medication adherence on the Lifestyle page — this helps identify what may be contributing to your readings.",
                "based_on_trend": trend.status,
            })

    elif trend.status == "low":
        recommendations.append({
            "message": "Your average blood pressure is on the low side. If you feel dizzy or unwell, contact your clinician.",
            "based_on_trend": "low",
        })

    else:  # controlled
        recommendations.append({
            "message": f"Your blood pressure has been controlled over the last {period_days} days. Keep up your current routine.",
            "based_on_trend": "controlled",
        })

    return recommendations