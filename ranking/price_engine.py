"""Value Index (TASK-015/P1-004): how good a deal a player is relative to
his role's peers, reduced from what used to be a second "maximum price you
should pay" competing with Auction Intelligence's — same unit (credits),
same name ("prezzo massimo"), routinely ~3x apart on a real player (Dimarco:
this module said max 33.2, Auction Intelligence said max 94.9, both shown
on the same screen, one of them marked a 🏆 Top player PASS). The
contradiction wasn't a "two points of view" thing, it was compute_fair_price
being anchored to a role's price *distribution* (P0-001's mixed price
scales skewed it low) while Auction Intelligence is anchored to this
player's own market price.

Auction Intelligence (ranking.auction_intelligence) is now the only source
for "how much can I bid" — this module deliberately no longer produces a
credit-denominated number at all, so it can never look like a second price
again. value_index is a plain ratio: 100 means exactly the role's median
efficiency, 130 means 30% more efficient than that median.
"""


def compute_value_index(value_for_money, median_value_for_money):
    """None when either input is missing or the median is zero — no
    population to compare against."""
    if not value_for_money or not median_value_for_money:
        return None
    return round(value_for_money / median_value_for_money * 100)
