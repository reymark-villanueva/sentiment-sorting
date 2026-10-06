"""Labelled sentences for checking the sentiment model: (text, expected label, language).

`CLEAR_ENGLISH` is the subset the automated tests assert on; the Tagalog / Taglish rows are
reported (per language) but not asserted, because the training data is mostly English.
"""

SAMPLES = [
    # --- positive (10) ---
    ("the librarian helped me find the book right away", "positive", "en"),
    ("borrowing and returning was fast and easy", "positive", "en"),
    ("the staff are friendly and very helpful", "positive", "en"),
    ("the study area is clean, quiet and comfortable", "positive", "en"),
    ("great collection and the wifi works perfectly", "positive", "en"),
    ("malinis at maayos ang library", "positive", "tl"),
    ("mabait at matulungin ang mga staff", "positive", "tl"),
    ("mabilis ang wifi at tahimik ang study area", "positive", "tl"),
    ("ang ganda ng library, thank you po sa mabilis na serbisyo", "positive", "taglish"),
    ("very helpful ang librarian, mabilis niyang nahanap ang libro ko", "positive", "taglish"),
    # --- negative (10) ---
    ("the wifi keeps dropping on the second floor", "negative", "en"),
    ("the staff were rude and ignored me", "negative", "en"),
    ("there are not enough computers and the printer is broken", "negative", "en"),
    ("the study area is too noisy and too hot", "negative", "en"),
    ("the line for borrowing books takes too long", "negative", "en"),
    ("mabagal ang internet kapag maraming gumagamit", "negative", "tl"),
    ("kulang ang mga computers", "negative", "tl"),
    ("masungit ang staff at mabagal kumilos", "negative", "tl"),
    ("nakakainis, walang available na table sa study area", "negative", "taglish"),
    ("sobrang init sa loob at sira ang aircon", "negative", "taglish"),
    # --- neutral (10) ---
    ("the library is open on weekdays", "neutral", "en"),
    ("the study area is on the second floor", "neutral", "en"),
    ("the library has computers and tables for students", "neutral", "en"),
    ("borrowing is limited to three books", "neutral", "en"),
    ("average experience, nothing special", "neutral", "en"),
    ("sakto lang ang facility", "neutral", "tl"),
    ("okay lang naman ang library", "neutral", "tl"),
    ("bukas ang library hanggang alas singko", "neutral", "tl"),
    ("may computer area sa second floor", "neutral", "taglish"),
    ("ayos lang ang wifi, minsan mabilis minsan mabagal", "neutral", "taglish"),
]

# Clear-cut English positives and negatives: the hard assertions in the tests.
CLEAR_ENGLISH = [(t, label) for t, label, lang in SAMPLES if lang == "en" and label in ("positive", "negative")]
