def classify_bp(systolic: int, diastolic: int) -> str:
    if systolic < 90 or diastolic < 60:
        return "low"
    elif systolic >= 150 or diastolic >=90:
        return "high"
    elif systolic >= 135 or diastolic >= 85:
        return "elevated"
    else:
        return "controlled"
    