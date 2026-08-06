"""Accounting layer - cash flows, shares, NAV, orders, fills, and return accounting.

All financial accounting logic that must satisfy daily accounting identities:
    NAV = cash + positions
    ΔNAV = market PnL + external flow - costs
    unit_nav = NAV / units
"""
