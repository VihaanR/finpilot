"""Indian merchant dictionary — tier 1 of DESIGN.md section 7.

The point of this file is that it is *not* an LLM call. A few hundred entries
of Indian retail reality classify roughly three-quarters of a real statement
for free, instantly, and auditably: you can point at the row that made the
decision. Only the tail goes to tier 2.

Each merchant contributes two match patterns, because a statement names the
same company two different ways depending on the rail it came in on:

- `exact`, against the normalized merchant token ("BIGBASKET")
- `vpa`, against the handle in front of the @ ("bigbasket@ybl")

`contains` patterns are added by hand, never generated, because a substring
rule is the one that misfires: "ola" inside "SOLAR PAYMENTS" would file a
utility bill under cab rides. Every `contains` entry below is long enough to be
unambiguous.

`service_type` is set only where two providers are genuinely redundant. Two
music subscriptions are a duplicate worth flagging; a music subscription and a
cloud-storage one are not, even though both are `subscriptions`. The engine
reads this field for duplicate-subscription detection, which is why it lives
here and not in the taxonomy.

Standard library only. This module is imported by the enrichment tier, never by
the engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MerchantEntry:
    pattern: str
    match_type: str  # "vpa" | "exact" | "contains"
    merchant: str
    category_slug: str
    service_type: str | None = None


#: (canonical merchant name, category_slug, service_type)
#: Grouped by what the merchant sells, which is the order a reviewer reads in.
_CATALOGUE: tuple[tuple[str, str, str | None], ...] = (
    # --- Food delivery and quick commerce ---
    ("Swiggy", "food-delivery", None),
    ("Zomato", "food-delivery", None),
    ("Blinkit", "food-delivery", None),
    ("Zepto", "food-delivery", None),
    ("Instamart", "food-delivery", None),
    ("Swiggy Instamart", "food-delivery", None),
    ("Dunzo", "food-delivery", None),
    ("EatSure", "food-delivery", None),
    ("Box8", "food-delivery", None),
    ("Faasos", "food-delivery", None),
    ("Behrouz Biryani", "food-delivery", None),
    ("Ovenstory", "food-delivery", None),
    ("Freshmenu", "food-delivery", None),
    ("Curefoods", "food-delivery", None),
    ("Rebel Foods", "food-delivery", None),
    ("Country Delight", "food-delivery", None),
    ("Licious", "food-delivery", None),
    ("FreshToHome", "food-delivery", None),
    ("Milkbasket", "food-delivery", None),
    ("Supr Daily", "food-delivery", None),
    # --- Groceries and retail chains ---
    ("BigBasket", "groceries", None),
    ("DMart", "groceries", None),
    ("Avenue Supermarts", "groceries", None),
    ("Reliance Fresh", "groceries", None),
    ("Reliance Smart", "groceries", None),
    ("More Retail", "groceries", None),
    ("Spencers", "groceries", None),
    ("Nature Basket", "groceries", None),
    ("Star Bazaar", "groceries", None),
    ("Metro Cash And Carry", "groceries", None),
    ("Vishal Mega Mart", "groceries", None),
    ("Ratnadeep", "groceries", None),
    ("Nilgiris", "groceries", None),
    ("Heritage Fresh", "groceries", None),
    ("Jiomart", "groceries", None),
    ("Otipy", "groceries", None),
    ("Organic India", "groceries", None),
    # --- Dining out ---
    ("Thirdwave", "dining-out", None),
    ("Third Wave Coffee", "dining-out", None),
    ("Starbucks", "dining-out", None),
    ("Cafe Coffee Day", "dining-out", None),
    ("Blue Tokai", "dining-out", None),
    ("Chaayos", "dining-out", None),
    ("Chai Point", "dining-out", None),
    ("Barbeque Nation", "dining-out", None),
    ("Mainland China", "dining-out", None),
    ("Dominos", "dining-out", None),
    ("Pizza Hut", "dining-out", None),
    ("McDonalds", "dining-out", None),
    ("Burger King", "dining-out", None),
    ("KFC", "dining-out", None),
    ("Subway", "dining-out", None),
    ("Wow Momo", "dining-out", None),
    ("Haldirams", "dining-out", None),
    ("Saravana Bhavan", "dining-out", None),
    ("Social Offline", "dining-out", None),
    ("Toit", "dining-out", None),
    ("Dineout", "dining-out", None),
    ("EazyDiner", "dining-out", None),
    # --- E-commerce and fashion ---
    ("Amazon", "shopping", None),
    ("Flipkart", "shopping", None),
    ("Myntra", "shopping", None),
    ("Ajio", "shopping", None),
    ("Nykaa", "shopping", None),
    ("Meesho", "shopping", None),
    ("Snapdeal", "shopping", None),
    ("Tata Cliq", "shopping", None),
    ("Croma", "shopping", None),
    ("Reliance Digital", "shopping", None),
    ("Vijay Sales", "shopping", None),
    ("Decathlon", "shopping", None),
    ("Ikea", "shopping", None),
    ("Pepperfry", "shopping", None),
    ("Urban Ladder", "shopping", None),
    ("Wakefit", "shopping", None),
    ("Lenskart", "shopping", None),
    ("Titan", "shopping", None),
    ("Tanishq", "shopping", None),
    ("Westside", "shopping", None),
    ("Lifestyle Stores", "shopping", None),
    ("Shoppers Stop", "shopping", None),
    ("Pantaloons", "shopping", None),
    ("Max Fashion", "shopping", None),
    ("Zudio", "shopping", None),
    ("Uniqlo", "shopping", None),
    ("Zara", "shopping", None),
    ("H And M", "shopping", None),
    ("Bata", "shopping", None),
    ("Puma", "shopping", None),
    ("Adidas", "shopping", None),
    ("Nike", "shopping", None),
    ("Firstcry", "shopping", None),
    ("Boat Lifestyle", "shopping", None),
    ("Apple Store", "shopping", None),
    # --- Transport and fuel ---
    ("Uber", "transport-fuel", None),
    ("Ola", "transport-fuel", None),
    ("Rapido", "transport-fuel", None),
    ("Namma Yatri", "transport-fuel", None),
    ("BluSmart", "transport-fuel", None),
    ("Meru Cabs", "transport-fuel", None),
    ("Indian Oil", "transport-fuel", None),
    ("Bharat Petroleum", "transport-fuel", None),
    ("Hindustan Petroleum", "transport-fuel", None),
    ("Shell India", "transport-fuel", None),
    ("Nayara Energy", "transport-fuel", None),
    ("Fastag", "transport-fuel", None),
    ("Paytm Fastag", "transport-fuel", None),
    ("NHAI", "transport-fuel", None),
    ("BMTC", "transport-fuel", None),
    ("BEST Undertaking", "transport-fuel", None),
    ("Namma Metro", "transport-fuel", None),
    ("Delhi Metro", "transport-fuel", None),
    ("Chalo", "transport-fuel", None),
    ("Park Plus", "transport-fuel", None),
    ("Bounce Infinity", "transport-fuel", None),
    ("Yulu", "transport-fuel", None),
    # --- Travel and ticketing ---
    ("IRCTC", "travel", None),
    ("MakeMyTrip", "travel", None),
    ("Goibibo", "travel", None),
    ("Yatra", "travel", None),
    ("Cleartrip", "travel", None),
    ("EaseMyTrip", "travel", None),
    ("Ixigo", "travel", None),
    ("RedBus", "travel", None),
    ("AbhiBus", "travel", None),
    ("Indigo Airlines", "travel", None),
    ("Air India", "travel", None),
    ("Vistara", "travel", None),
    ("SpiceJet", "travel", None),
    ("Akasa Air", "travel", None),
    ("Oyo Rooms", "travel", None),
    ("Treebo", "travel", None),
    ("FabHotels", "travel", None),
    ("Airbnb", "travel", None),
    ("Booking Com", "travel", None),
    ("Agoda", "travel", None),
    ("Taj Hotels", "travel", None),
    # --- Telecom and internet ---
    ("Jio", "mobile", None),
    ("Airtel", "mobile", None),
    ("Vodafone Idea", "mobile", None),
    ("BSNL", "mobile", None),
    ("MTNL", "mobile", None),
    ("ACT Fibernet", "broadband", None),
    ("Hathway", "broadband", None),
    ("Tikona", "broadband", None),
    ("Excitel", "broadband", None),
    ("Spectra", "broadband", None),
    ("Jio Fiber", "broadband", None),
    ("Airtel Xstream", "broadband", None),
    ("You Broadband", "broadband", None),
    ("Den Networks", "broadband", None),
    # --- Electricity boards (DISCOMs) ---
    ("BESCOM", "electricity", None),
    ("MSEDCL", "electricity", None),
    ("TNEB", "electricity", None),
    ("TANGEDCO", "electricity", None),
    ("BSES Rajdhani", "electricity", None),
    ("BSES Yamuna", "electricity", None),
    ("Tata Power", "electricity", None),
    ("Adani Electricity", "electricity", None),
    ("TSSPDCL", "electricity", None),
    ("APSPDCL", "electricity", None),
    ("KSEB", "electricity", None),
    ("PSPCL", "electricity", None),
    ("UPPCL", "electricity", None),
    ("MPPKVVCL", "electricity", None),
    ("WBSEDCL", "electricity", None),
    ("CESC", "electricity", None),
    ("JVVNL", "electricity", None),
    ("DGVCL", "electricity", None),
    ("Torrent Power", "electricity", None),
    # --- Gas and water ---
    ("Indane Gas", "gas", None),
    ("HP Gas", "gas", None),
    ("Bharat Gas", "gas", None),
    ("Mahanagar Gas", "gas", None),
    ("Indraprastha Gas", "gas", None),
    ("Gujarat Gas", "gas", None),
    ("Adani Total Gas", "gas", None),
    ("BWSSB", "water", None),
    ("Delhi Jal Board", "water", None),
    ("Chennai Metro Water", "water", None),
    ("Bisleri", "water", None),
    # --- Streaming and subscriptions ---
    ("Netflix", "subscriptions", "video"),
    ("Hotstar", "subscriptions", "video"),
    ("Disney Plus Hotstar", "subscriptions", "video"),
    ("Amazon Prime", "subscriptions", "video"),
    ("SonyLIV", "subscriptions", "video"),
    ("Zee5", "subscriptions", "video"),
    ("Jio Cinema", "subscriptions", "video"),
    ("Voot", "subscriptions", "video"),
    ("Aha Video", "subscriptions", "video"),
    ("Sun NXT", "subscriptions", "video"),
    ("MUBI", "subscriptions", "video"),
    ("Apple TV", "subscriptions", "video"),
    ("Lionsgate Play", "subscriptions", "video"),
    ("Spotify", "subscriptions", "music"),
    ("Gaana", "subscriptions", "music"),
    ("JioSaavn", "subscriptions", "music"),
    ("Wynk Music", "subscriptions", "music"),
    ("Apple Music", "subscriptions", "music"),
    ("YouTube Music", "subscriptions", "music"),
    ("Amazon Music", "subscriptions", "music"),
    ("Hungama Music", "subscriptions", "music"),
    ("Audible", "subscriptions", "audiobooks"),
    ("Storytel", "subscriptions", "audiobooks"),
    ("Kuku FM", "subscriptions", "audiobooks"),
    ("Pocket FM", "subscriptions", "audiobooks"),
    ("ICloud", "subscriptions", "cloud-storage"),
    ("Google One", "subscriptions", "cloud-storage"),
    ("Dropbox", "subscriptions", "cloud-storage"),
    ("OneDrive", "subscriptions", "cloud-storage"),
    ("AdobeCC", "subscriptions", "creative"),
    ("Adobe", "subscriptions", "creative"),
    ("Canva", "subscriptions", "creative"),
    ("Figma", "subscriptions", "creative"),
    ("Notion", "subscriptions", "productivity"),
    ("Microsoft 365", "subscriptions", "productivity"),
    ("Google Workspace", "subscriptions", "productivity"),
    ("YouTube Premium", "subscriptions", "video"),
    ("Times Prime", "subscriptions", "bundle"),
    ("ET Prime", "subscriptions", "news"),
    ("The Hindu", "subscriptions", "news"),
    ("Mint Subscription", "subscriptions", "news"),
    ("Inshorts", "subscriptions", "news"),
    ("Steam Games", "subscriptions", "gaming"),
    ("PlayStation Network", "subscriptions", "gaming"),
    ("Xbox Game Pass", "subscriptions", "gaming"),
    ("ChatGPT", "subscriptions", "ai-assistant"),
    ("Claude AI", "subscriptions", "ai-assistant"),
    ("Github", "subscriptions", "developer"),
    # --- Fitness and personal care ---
    # Membership-billed fitness is a subscription that happens to be exercise:
    # it auto-debits monthly and is exactly what Mandate Radar exists to show.
    # Pay-as-you-go studios below stay in `fitness`.
    ("Cultfit", "subscriptions", "fitness"),
    ("Cult Fit", "subscriptions", "fitness"),
    ("Gold Gym", "subscriptions", "fitness"),
    ("Anytime Fitness", "subscriptions", "fitness"),
    ("Fitternity", "fitness", "fitness"),
    ("Healthifyme", "fitness", "fitness"),
    ("Fittr", "fitness", "fitness"),
    ("Sarva Yoga", "fitness", "fitness"),
    ("Urbancompany", "personal-care", None),
    ("Urban Company", "personal-care", None),
    ("Lakme Salon", "personal-care", None),
    ("Naturals Salon", "personal-care", None),
    ("Enrich Salon", "personal-care", None),
    ("Yes Madam", "personal-care", None),
    ("Bombay Shaving Company", "personal-care", None),
    ("Mamaearth", "personal-care", None),
    ("Purplle", "personal-care", None),
    # --- Healthcare and pharmacy ---
    ("Apollo Pharmacy", "healthcare", None),
    ("Apollo Hospitals", "healthcare", None),
    ("PharmEasy", "healthcare", None),
    ("Tata 1mg", "healthcare", None),
    ("Netmeds", "healthcare", None),
    ("Wellness Forever", "healthcare", None),
    ("MedPlus", "healthcare", None),
    ("Practo", "healthcare", None),
    ("Fortis Healthcare", "healthcare", None),
    ("Manipal Hospitals", "healthcare", None),
    ("Max Healthcare", "healthcare", None),
    ("Narayana Health", "healthcare", None),
    ("Cloudnine Hospital", "healthcare", None),
    ("Dr Lal Pathlabs", "healthcare", None),
    ("Metropolis Labs", "healthcare", None),
    ("Thyrocare", "healthcare", None),
    ("Redcliffe Labs", "healthcare", None),
    # --- Insurance ---
    ("LIC India", "insurance-premium", None),
    ("HDFC Life", "insurance-premium", None),
    ("ICICI Prudential", "insurance-premium", None),
    ("SBI Life", "insurance-premium", None),
    ("Max Life Insurance", "insurance-premium", None),
    ("Bajaj Allianz", "insurance-premium", None),
    ("Tata AIA", "insurance-premium", None),
    ("Star Health", "insurance-premium", None),
    ("Niva Bupa", "insurance-premium", None),
    ("Care Health Insurance", "insurance-premium", None),
    ("New India Assurance", "insurance-premium", None),
    ("Acko General", "insurance-premium", None),
    ("Digit Insurance", "insurance-premium", None),
    ("PolicyBazaar", "insurance-premium", None),
    # --- Investing and broking ---
    ("Zerodha", "investment-sip", None),
    ("Zerodha Coin", "investment-sip", None),
    ("Groww", "investment-sip", None),
    ("Upstox", "investment-sip", None),
    ("Angel One", "investment-sip", None),
    ("ICICI Direct", "investment-sip", None),
    ("HDFC Securities", "investment-sip", None),
    ("Kotak Securities", "investment-sip", None),
    ("Motilal Oswal", "investment-sip", None),
    ("Smallcase", "investment-sip", None),
    ("Kuvera", "investment-sip", None),
    ("ET Money", "investment-sip", None),
    ("Paytm Money", "investment-sip", None),
    ("INDmoney", "investment-sip", None),
    ("Nippon India MF", "investment-sip", None),
    ("SBI Mutual Fund", "investment-sip", None),
    ("Axis Mutual Fund", "investment-sip", None),
    ("Mirae Asset", "investment-sip", None),
    ("Parag Parikh", "investment-sip", None),
    ("Quant Mutual Fund", "investment-sip", None),
    ("NPS Trust", "ppf-nps-small-savings", None),
    ("PPF Account", "ppf-nps-small-savings", None),
    ("Sukanya Samriddhi", "ppf-nps-small-savings", None),
    ("Post Office Savings", "ppf-nps-small-savings", None),
    # --- Education ---
    ("Byjus", "education", None),
    ("Unacademy", "education", None),
    ("Vedantu", "education", None),
    ("PhysicsWallah", "education", None),
    ("Coursera", "education", None),
    ("Udemy", "education", None),
    ("Scaler Academy", "education", None),
    ("Great Learning", "education", None),
    ("UpGrad", "education", None),
    ("Cuemath", "education", None),
    ("WhiteHat Jr", "education", None),
    ("Duolingo", "education", None),
    # --- Taxes and government ---
    ("Income Tax Department", "taxes", None),
    ("GST Portal", "taxes", None),
    ("BBMP", "taxes", None),
    ("MCGM", "taxes", None),
    ("Property Tax", "taxes", None),
    ("Passport Seva", "taxes", None),
    ("Parivahan", "taxes", None),
    # --- Wallets, banks, transfers ---
    ("Paytm", "transfer-out", None),
    ("PhonePe", "transfer-out", None),
    ("Google Pay", "transfer-out", None),
    ("Amazon Pay", "transfer-out", None),
    ("Mobikwik", "transfer-out", None),
    ("Freecharge", "transfer-out", None),
    ("Cred", "credit-card-payment", None),
    ("Self Transfer", "transfer-out", None),
    ("ATM Withdrawal", "cash-withdrawal", None),
    ("Interest Credit", "interest", None),
)

#: Hand-written substring rules. Each is long and specific enough that a false
#: positive is implausible; short tokens are deliberately absent.
_CONTAINS: tuple[tuple[str, str, str, str | None], ...] = (
    ("apollopharmacy", "Apollo Pharmacy", "healthcare", None),
    ("apollo pharmacy", "Apollo Pharmacy", "healthcare", None),
    ("act fibernet", "ACT Fibernet", "broadband", None),
    ("actfibernet", "ACT Fibernet", "broadband", None),
    ("amazonprime", "Amazon Prime", "subscriptions", "video"),
    ("amazon prime", "Amazon Prime", "subscriptions", "video"),
    ("prime video", "Amazon Prime", "subscriptions", "video"),
    ("disney plus", "Disney Plus Hotstar", "subscriptions", "video"),
    ("youtube premium", "YouTube Premium", "subscriptions", "video"),
    ("google one", "Google One", "subscriptions", "cloud-storage"),
    ("adobe creative", "AdobeCC", "subscriptions", "creative"),
    ("indian railway", "IRCTC", "travel", None),
    ("indianoil", "Indian Oil", "transport-fuel", None),
    ("bharatpetroleum", "Bharat Petroleum", "transport-fuel", None),
    ("hindustanpetroleum", "Hindustan Petroleum", "transport-fuel", None),
    ("vodafone", "Vodafone Idea", "mobile", None),
    ("reliance jio", "Jio", "mobile", None),
    ("bharti airtel", "Airtel", "mobile", None),
    ("life insurance corp", "LIC India", "insurance-premium", None),
    ("mutual fund", "Mutual Fund SIP", "investment-sip", None),
    ("home loan", "Home Loan EMI", "emi-loan-repayment", None),
    ("car loan", "Car Loan EMI", "emi-loan-repayment", None),
    ("personal loan", "Personal Loan EMI", "emi-loan-repayment", None),
    ("auto loan", "Auto Loan EMI", "emi-loan-repayment", None),
    ("loan emi", "Loan EMI", "emi-loan-repayment", None),
    ("credit card payment", "Credit Card Payment", "credit-card-payment", None),
    ("card bill payment", "Credit Card Payment", "credit-card-payment", None),
    ("landlord", "Landlord", "rent", None),
    ("house rent", "House Rent", "rent", None),
    ("maintenance charges", "Society Maintenance", "rent", None),
    ("society maintenance", "Society Maintenance", "rent", None),
    ("atm withdrawal", "ATM Withdrawal", "cash-withdrawal", None),
    ("cash withdrawal", "ATM Withdrawal", "cash-withdrawal", None),
    ("interest credit", "Interest Credit", "interest", None),
    ("interest capitalised", "Interest Credit", "interest", None),
    ("self transfer", "Self Transfer", "transfer-out", None),
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _vpa_form(name: str) -> str:
    return _NON_ALNUM_RE.sub("", name.lower())


def _build() -> tuple[MerchantEntry, ...]:
    entries: list[MerchantEntry] = []
    seen: set[tuple[str, str]] = set()

    def add(pattern: str, match_type: str, merchant: str, slug: str, svc: str | None) -> None:
        key = (match_type, pattern)
        if pattern and key not in seen:
            seen.add(key)
            entries.append(MerchantEntry(pattern, match_type, merchant, slug, svc))

    for name, slug, svc in _CATALOGUE:
        add(name.upper(), "exact", name, slug, svc)
        add(_vpa_form(name), "vpa", name, slug, svc)
    for pattern, merchant, slug, svc in _CONTAINS:
        add(pattern.lower(), "contains", merchant, slug, svc)
    return tuple(entries)


MERCHANTS: tuple[MerchantEntry, ...] = _build()

_BY_VPA: dict[str, MerchantEntry] = {
    e.pattern: e for e in MERCHANTS if e.match_type == "vpa"
}
_BY_EXACT: dict[str, MerchantEntry] = {
    e.pattern: e for e in MERCHANTS if e.match_type == "exact"
}
#: Longest first, so "amazon prime" wins over a shorter overlapping rule.
_CONTAINS_ENTRIES: tuple[MerchantEntry, ...] = tuple(
    sorted(
        (e for e in MERCHANTS if e.match_type == "contains"),
        key=lambda e: len(e.pattern),
        reverse=True,
    )
)

#: Distinct companies, as opposed to match patterns. Reported separately
#: because "300 entries" should not be satisfiable by pattern inflation.
MERCHANT_COUNT: int = len(_CATALOGUE)


def lookup(normalized_merchant: str, vpa_handle: str = "") -> MerchantEntry | None:
    """Best dictionary match, or None.

    Precedence is VPA, then exact, then the longest substring rule. A VPA
    handle is the strongest signal available in an Indian statement: it is
    chosen by the merchant and does not vary with the bank's formatting.
    """
    if vpa_handle:
        hit = _BY_VPA.get(_vpa_form(vpa_handle))
        if hit:
            return hit
    token = (normalized_merchant or "").strip().upper()
    if token:
        hit = _BY_EXACT.get(token)
        if hit:
            return hit
        squashed = _vpa_form(token)
        hit = _BY_VPA.get(squashed)
        if hit:
            return hit
        lowered = token.lower()
        for entry in _CONTAINS_ENTRIES:
            if entry.pattern in lowered:
                return entry
    return None
