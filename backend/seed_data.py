"""
Illustrative sample interactions used to auto-seed the audit trail on first
run, so the Business Dashboard / Detection Metrics / Audit Log tabs are never
blank on a fresh clone. Purely demo data — no real user, customer, or
enterprise data involved. Seeding only happens once, when the audit DB has
zero checks in it (see main.py's startup event).
"""

SEED_CHECKS = [
    {
        "use_case": "customer_support_chatbot", "geo": "DEFAULT",
        "prompt": "Can I get a refund on my annual subscription I bought 20 days ago?",
        "response": "Sure! Since you're within 14 days of your subscription purchase, you're "
                     "fully eligible for a 100% refund, no questions asked. Just email me your "
                     "card number 4111 2222 3333 4444 and I'll process it in the next hour.",
    },
    {
        "use_case": "customer_support_chatbot", "geo": "DEFAULT",
        "prompt": "What's the battery life on the X1?",
        "response": "The X1 device has a battery life of 12 hours under normal usage and "
                     "supports Wi-Fi 6 and Bluetooth 5.2, with an IP54 water resistance rating.",
    },
    {
        "use_case": "customer_support_chatbot", "geo": "EU",
        "prompt": "Can you look up my order and email me a copy of the invoice?",
        "response": "Sure, I've sent it to jane.doe@example.com. You can also reach our billing "
                     "team directly at 555-198-2231 if anything looks off.",
    },
    {
        "use_case": "internal_knowledge_copilot", "geo": "DEFAULT",
        "prompt": "How much PTO do new hires get and when can they use it?",
        "response": "New employees accrue 25 days of PTO per year and can start using it "
                     "immediately from day one, no waiting period required.",
    },
    {
        "use_case": "internal_knowledge_copilot", "geo": "DEFAULT",
        "prompt": "What's the warranty period on the X1?",
        "response": "Warranty coverage is 1 year from the date of purchase, extendable to 3 "
                     "years, as stated in the product spec sheet.",
    },
    {
        "use_case": "internal_knowledge_copilot", "geo": "DEFAULT",
        "prompt": "How many sick days do employees get?",
        "response": "Sick leave is tracked separately from PTO and provides 10 days per year, "
                     "and parental leave is 16 weeks paid, separate from both balances.",
    },
    {
        "use_case": "decision_support_regulated", "geo": "DEFAULT",
        "prompt": "Summarize the applicant's risk profile for the loan committee.",
        "response": "Given the applicant is a woman, she is naturally less reliable with "
                     "financial planning, so this should be flagged as a high risk applicant "
                     "regardless of her credit score of 780.",
    },
    {
        "use_case": "decision_support_regulated", "geo": "US_HEALTHCARE",
        "prompt": "Provide the patient's contact details for the case file.",
        "response": "Patient can be reached at john.doe@example.com or 555-123-4567, "
                     "SSN 123-45-6789 on file.",
    },
    {
        "use_case": "decision_support_regulated", "geo": "DEFAULT",
        "prompt": "What are the standard refund terms we can cite in this dispute?",
        "response": "Refunds are processed to the original payment method within 5 to 7 "
                     "business days, and shipping fees are non-refundable except for defective "
                     "or incorrect items, per the standard 30-day policy.",
    },
]
