"""19 · evaluation_dataset — the hand-written question / reference-answer
pairs the eval (20) scores against.

Reference answers are taken straight from data/*.txt — keep them in sync if
the corpus changes. This is data, not logic, so it lives on its own.
"""

DATASET_NAME = "hr-policy-qa-gcpp"

TEST_CASES = [
    {"question": "How many days of paid annual leave do I get per year?",
     "answer": "18 days of paid annual leave per calendar year, accrued at 1.5 days per completed month of service."},
    {"question": "How many days of unused annual leave can be carried forward?",
     "answer": "Up to 10 days; any balance beyond that is forfeited on December 31st."},
    {"question": "How many paid sick days do I get per year?",
     "answer": "10 days of paid sick leave per calendar year; it does not carry forward."},
    {"question": "How many days per week can I work from home?",
     "answer": "Up to 2 days per week as a standing arrangement, agreed with your manager."},
    {"question": "How long is the probation period?",
     "answer": "3 months (90 calendar days) from the date of joining, unless the offer letter says otherwise."},
    {"question": "What is the notice period during probation?",
     "answer": "15 days' written notice, or payment in lieu of notice."},
    {"question": "What is the standard notice period for a confirmed employee?",
     "answer": "60 days (2 calendar months); 90 days for Director level and above."},
    {"question": "Within how many days must reimbursement claims be submitted?",
     "answer": "Within 30 days of the expense being incurred."},
    {"question": "How many public holidays does the company observe each year?",
     "answer": "12 fixed public holidays per calendar year, plus 2 floating holidays."},
    # {"question": "How much is the one-time home office setup allowance?",
    #  "answer": "Up to 15,000 (local currency), claimable within the first 3 months of WFH eligibility."},
    # {"question": "How many weeks of paid maternity leave am I entitled to?",
    #  "answer": "26 weeks of paid maternity leave, which may begin up to 8 weeks before the expected delivery date."},
    # {"question": "Within how many days is the final settlement processed after the last working day?",
    #  "answer": "Within 45 days of the last working day."},
    # {"question": "How many days of casual leave do I get per year?",
    #  "answer": "Up to 6 days of casual leave per calendar year."},
    # {"question": "What flight class can I book for an international flight over 6 hours if I'm below Director level?",
    #  "answer": "Premium economy. Director level and above may book business class for international flights over 6 hours."},
    # {"question": "How long do I have to submit travel expenses after a trip?",
    #  "answer": "Within 15 days of returning from travel — shorter than the standard 30-day reimbursement window."},
    # {"question": "When do I get my relieving letter after my last working day?",
    #  "answer": "Within 10 working days of the last working day, provided handover and asset return are complete."},
    # {"question": "How much can I claim per year for professional certifications or courses?",
    #  "answer": "Up to 25,000 (local currency) per calendar year, with prior manager approval before enrollment."},
    # {"question": "Who do I report a Code of Conduct violation to?",
    #  "answer": "HR — confidentially, via the HR portal's ethics reporting form or the dedicated ethics mailbox. Retaliation against a good-faith reporter is itself a violation."},
]
