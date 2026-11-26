"""Patient-facing safety wording shared by runtime and clinical review.

These messages are intentionally separate from lifestyle guidance. Low and
very-high recommendation routes use only these safety statements; they never
attach a model estimate or habit advice. The wording remains unsigned until
the clinical-review sheet is approved.
"""

LOW_SAFETY_GUIDANCE = (
    "If you feel dizzy, faint or unwell, contact your clinician. Seek urgent care if the symptoms are severe. "
    "Lifestyle advice is not shown for low readings."
)

VERY_HIGH_SAFETY_GUIDANCE = (
    "Seek urgent medical care. If you have chest pain, a severe headache, trouble breathing, weakness, or vision "
    "changes, tell the emergency service. Lifestyle advice is not shown for very high readings."
)
