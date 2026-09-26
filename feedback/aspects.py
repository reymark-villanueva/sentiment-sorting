"""
Quick Aspect chip text for the feedback wizard's Step 2 — tailored per library
service so students tag something concrete ("Frequent Connection Drops" for
Wi-Fi) instead of a one-size-fits-all list. Each service gets 21 aspects:
7 negative, 7 neutral, 7 positive.
"""

import random

SERVICE_ASPECTS = {
    'Facilities': {
        'negative': [
            'Restrooms Need Cleaning',
            'Broken Air Conditioning',
            'Not Enough Seating',
            'Poor Lighting',
            'Leaking Roof/Ceiling',
            'Too Noisy for Studying',
            'Furniture Needs Repair',
        ],
        'neutral': [
            'Adequate Seating Capacity',
            'Standard Lighting Conditions',
            'Average Room Temperature',
            'Typical Cleanliness Level',
            'Ordinary Furniture Condition',
            'Moderate Noise Level',
            'Basic Restroom Facilities',
        ],
        'positive': [
            'Clean & Well-Maintained',
            'Cold, Comfortable Air Conditioning',
            'Spacious Seating Areas',
            'Bright, Well-Lit Spaces',
            'Quiet Study Atmosphere',
            'Modern, Comfortable Furniture',
            'Well-Maintained Restrooms',
        ],
    },
    'Library Staff': {
        'negative': [
            'Unhelpful Staff Response',
            'Long Wait for Assistance',
            'Impolite Staff Behavior',
            'Staff Lacked Product Knowledge',
            'Slow Service at Counter',
            'Staff Seemed Disinterested',
            'Difficult to Locate Staff',
        ],
        'neutral': [
            'Average Response Time',
            'Standard Staff Assistance',
            'Adequate Staff Availability',
            'Typical Counter Service',
            'Ordinary Level of Courtesy',
            'Moderate Staff Knowledge',
            'Usual Waiting Time',
        ],
        'positive': [
            'Courteous Librarians',
            'Prompt & Helpful Assistance',
            'Knowledgeable Staff',
            'Friendly Customer Service',
            'Quick Response at Counter',
            'Staff Went Above and Beyond',
            'Easy to Approach Staff',
        ],
    },
    'Internet/Wi-Fi': {
        'negative': [
            'Needs Faster Wi-Fi',
            'Frequent Connection Drops',
            'Weak Signal in Some Areas',
            'Wi-Fi Often Unavailable',
            'Slow Download Speeds',
            'Difficult Network Login',
            'Limited Bandwidth at Peak Hours',
        ],
        'neutral': [
            'Average Connection Speed',
            'Standard Wi-Fi Coverage',
            'Typical Signal Strength',
            'Adequate for Basic Browsing',
            'Moderate Network Reliability',
            'Usual Login Process',
            'Ordinary Bandwidth Availability',
        ],
        'positive': [
            'Fast & Stable Connection',
            'Reliable Wi-Fi Coverage',
            'Strong Signal Throughout',
            'Quick & Easy Network Login',
            'No Connectivity Issues',
            'Great Speed for Research',
            'Consistent Uptime',
        ],
    },
    'Computer Services': {
        'negative': [
            'Outdated Computer Units',
            'Frequent System Crashes',
            'Not Enough Computer Units',
            'Slow Software Performance',
            'Printer Often Out of Service',
            'Missing Software Applications',
            'Long Queue for Computer Use',
        ],
        'neutral': [
            'Average Computer Performance',
            'Standard Software Availability',
            'Adequate Number of Units',
            'Typical Printing Service',
            'Ordinary System Speed',
            'Moderate Wait for Availability',
            'Usual Hardware Condition',
        ],
        'positive': [
            'Fast, Reliable Computers',
            'Up-to-Date Software',
            'Ample Computer Units Available',
            'Smooth Printing Service',
            'Well-Maintained Hardware',
            'No Downtime Experienced',
            'Efficient System Performance',
        ],
    },
    'Borrowing & Returning': {
        'negative': [
            'Limited Book Availability',
            'Long Borrowing Queue',
            'Confusing Return Process',
            'Frequent System Errors at Checkout',
            'Overdue Fee Confusion',
            'Books Often Already Borrowed',
            'Slow Checkout Processing',
        ],
        'neutral': [
            'Average Borrowing Wait Time',
            'Standard Return Procedure',
            'Typical Book Availability',
            'Adequate Checkout Speed',
            'Ordinary Renewal Process',
            'Moderate Queue Length',
            'Usual Due-Date Policy',
        ],
        'positive': [
            'Wide Book Selection Available',
            'Quick & Easy Checkout',
            'Hassle-Free Returns',
            'Efficient Borrowing System',
            'Clear Renewal Process',
            'Well-Organized Book Catalog',
            'Fast Processing at Counter',
        ],
    },
    'Study Areas': {
        'negative': [
            'Not Enough Study Spaces',
            'Too Crowded During Peak Hours',
            'Noisy Study Environment',
            'Uncomfortable Seating',
            'Poor Ventilation',
            'Limited Group Study Rooms',
            'Difficult to Reserve a Space',
        ],
        'neutral': [
            'Adequate Number of Study Spaces',
            'Standard Seating Comfort',
            'Average Noise Level',
            'Typical Room Temperature',
            'Ordinary Availability of Spaces',
            'Moderate Crowd During the Day',
            'Usual Reservation Process',
        ],
        'positive': [
            'Quiet Study Atmosphere',
            'Plenty of Study Spaces',
            'Comfortable Seating',
            'Well-Ventilated Rooms',
            'Easy Room Reservation',
            'Great for Group Study',
            'Peaceful, Focused Environment',
        ],
    },
    'Online Resources': {
        'negative': [
            'Difficult to Access E-Resources',
            'Limited Database Subscriptions',
            'Confusing Online Catalog',
            'Frequent Access Errors',
            'Outdated Digital Collection',
            'Slow-Loading E-Books',
            'Login Issues for Online Portal',
        ],
        'neutral': [
            'Average Database Selection',
            'Standard Online Catalog Usability',
            'Adequate E-Resource Access',
            'Typical Loading Speed',
            'Ordinary Digital Collection Size',
            'Moderate Login Reliability',
            'Usual Portal Navigation',
        ],
        'positive': [
            'Easy Access to E-Resources',
            'Extensive Database Selection',
            'User-Friendly Online Catalog',
            'Up-to-Date Digital Collection',
            'Fast E-Book Loading',
            'Reliable Online Portal',
            'Smooth Login Experience',
        ],
    },
    'Other': {
        'negative': [
            'General Inconvenience Experienced',
            'Unclear Signage/Directions',
            'Limited Operating Hours',
            'Difficulty Finding Information',
            'Unresolved Concern',
            'Needs Improvement Overall',
            'Miscellaneous Issue Encountered',
        ],
        'neutral': [
            'Average Overall Experience',
            'Standard Service Encountered',
            'Typical Library Visit',
            'Adequate for My Needs',
            'Ordinary Overall Impression',
            'Moderate Satisfaction Level',
            'Usual Library Experience',
        ],
        'positive': [
            'Great Overall Experience',
            'Helpful in General',
            'Convenient Operating Hours',
            'Clear Signage & Directions',
            'Positive Overall Impression',
            'Exceeded My Expectations',
            'Would Recommend to Others',
        ],
    },
}

DEFAULT_ASPECTS = SERVICE_ASPECTS['Other']


def aspects_by_service_id(services):
    """
    Map each service's pk (as a string, for JS/JSON key use) to a single flat,
    pre-shuffled list of its 21 aspect phrases — shuffled here (server-side,
    fresh per request) rather than left grouped by sentiment, so the negative/
    neutral/positive blocks never appear in the source order the frontend
    receives, regardless of what the client does with it.
    """
    result = {}
    for service in services:
        aspect_set = SERVICE_ASPECTS.get(service.name, DEFAULT_ASPECTS)
        flat = [
            {'phrase': phrase, 'sentiment': sentiment}
            for sentiment, phrases in aspect_set.items()
            for phrase in phrases
        ]
        random.shuffle(flat)
        result[str(service.pk)] = flat
    return result
