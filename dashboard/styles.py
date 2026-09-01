import streamlit as st

# Apple-style palette: neutral-gray button accent, off-white surfaces,
# near-black text — same tokens the global CSS and the player-card CSS both
# draw from. Named "APPLE_BLUE" for historical reasons but intentionally
# gray, matching Apple's muted secondary-button style rather than the
# brighter iOS system blue.
APPLE_BLUE = "#6e6e73"
APPLE_BLUE_DARK = "#525256"
APPLE_INK = "#1d1d1f"
APPLE_GRAY = "#6e6e73"
APPLE_TERTIARY = "#86868b"
APPLE_SURFACE = "#f5f5f7"
APPLE_BORDER = "#e5e5e7"
# True accent blue (grafica.md sez. 21): reserved for links/interactive
# text like "Vedi scheda →", never for large button surfaces — those stay
# the neutral APPLE_BLUE gray above.
APPLE_ACCENT = "#0071e3"
APPLE_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', "
    "'Helvetica Neue', Helvetica, Arial, sans-serif"
)


def inject_global_css() -> None:
    """Apple-like visual theme applied across every page: SF-style font
    stack, neutral surfaces, system-blue accent, rounded corners and soft
    shadows on Streamlit's native widgets (buttons, metrics, inputs,
    tables). Safe to call multiple times per run (st.markdown just appends
    another <style> block)."""
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: {APPLE_FONT_STACK};
        }}
        [data-testid="stAppViewContainer"] {{
            background: {APPLE_SURFACE};
        }}
        [data-testid="stMain"] .block-container {{
            max-width: 1440px;
        }}
        [data-testid="stHeader"] {{
            background: rgba(255,255,255,0.8);
            backdrop-filter: saturate(180%) blur(12px);
        }}
        [data-testid="stSidebar"] {{
            background: {APPLE_SURFACE};
            border-right: 1px solid #e5e5ea;
        }}
        h1, h2, h3 {{
            color: {APPLE_INK};
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        p, span, label, div {{
            color: {APPLE_INK};
        }}
        [data-testid="stCaptionContainer"], .stCaption {{
            color: {APPLE_GRAY} !important;
        }}
        button[kind], .stButton button, .stDownloadButton > button {{
            border-radius: 980px;
            border: 1px solid {APPLE_BLUE};
            background: {APPLE_BLUE};
            color: #ffffff;
            font-weight: 500;
            font-size: 15px;
            transition: background 0.15s ease, transform 0.1s ease;
        }}
        /* The button's own text sits in a nested p/span, and the blanket
        "p, span, label, div" ink-color rule above matches that inner
        element directly — a direct match beats color merely inherited from
        the button, so button labels were rendering in dark ink on a
        dark-gray background instead of white. !important forces white
        regardless of nesting depth. */
        button[kind] *, .stButton button *, .stDownloadButton > button * {{
            color: #ffffff !important;
        }}
        .stButton button:hover, .stDownloadButton > button:hover {{
            background: {APPLE_BLUE_DARK};
            border-color: {APPLE_BLUE_DARK};
            transform: translateY(-1px);
        }}
        [data-testid="stMetric"] {{
            background: {APPLE_SURFACE};
            border-radius: 18px;
            padding: 14px 16px;
            border: 1px solid #e5e5ea;
        }}
        [data-testid="stMetricValue"] {{
            color: {APPLE_INK};
            font-weight: 600;
        }}
        [data-testid="stMetricLabel"] {{
            color: {APPLE_GRAY};
        }}
        div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="base-input"] {{
            border-radius: 12px !important;
        }}
        [data-testid="stExpander"] {{
            border-radius: 14px;
            border: 1px solid #e5e5ea;
        }}
        [data-testid="stTable"], .stTable {{
            border-radius: 14px;
            overflow: hidden;
        }}
        hr, [data-testid="stDivider"] {{
            border-color: #e5e5ea;
        }}
        [data-testid="stAlert"] {{
            border-radius: 14px;
            border: none;
        }}
        .fc-ideal-menu-marker {{
            font-weight: 600;
            padding: 8px 10px;
            border-radius: 10px;
            cursor: default;
            color: {APPLE_INK};
        }}
        .fc-ideal-menu-marker:hover {{
            background: #e5e5ea;
        }}
        [data-testid="stSidebar"] div[data-testid="element-container"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"] {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.2s ease-in;
            margin-top: -6px;
        }}
        [data-testid="stSidebar"] div[data-testid="element-container"]:has(.fc-ideal-menu-marker):hover + div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.fc-ideal-menu-marker):hover + div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.fc-ideal-menu-marker):hover,
        [data-testid="stSidebar"] div[data-testid="element-container"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"]:hover,
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
            max-height: 900px;
        }}
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] .stButton button {{
            background: transparent;
            border: none;
            color: {APPLE_INK};
            font-weight: 400;
            text-align: left;
            justify-content: flex-start;
            padding: 4px 10px 4px 22px;
            border-radius: 8px;
        }}
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] .stButton button:hover {{
            background: #e5e5ea;
            transform: none;
        }}
        /* Streamlit tronca nativamente la lista pagine della sidebar a
        max-height:30vh (con un pulsante "View more"/"View less") quando la
        sidebar contiene anche altri elementi — qui il widget Rosa Ideale.
        Vogliamo sempre tutte le pagine visibili senza dover cliccare. */
        [data-testid="stSidebarNavItems"] {{
            max-height: none !important;
            overflow: visible !important;
        }}
        [data-testid="stSidebarNavViewButton"] {{
            display: none !important;
        }}

        /* --- Page header (grafica.md sez. 24-25) --- */
        .fc-page-title {{
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -1px;
            color: {APPLE_INK};
            margin-bottom: 8px;
        }}
        .fc-page-meta {{
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            color: {APPLE_GRAY};
            margin-bottom: 20px;
        }}

        /* --- Pagination (sez. 26): small circular ‹ › buttons, right
        after .fc-pager-marker. --- */
        div[data-testid="element-container"]:has(.fc-pager-marker) + div[data-testid="element-container"] .stButton button,
        div[data-testid="stElementContainer"]:has(.fc-pager-marker) + div[data-testid="stElementContainer"] .stButton button {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            padding: 0;
            background: {APPLE_SURFACE} !important;
            border: 1px solid {APPLE_BORDER} !important;
            color: {APPLE_INK} !important;
            font-weight: 600;
        }}
        div[data-testid="element-container"]:has(.fc-pager-marker) + div[data-testid="element-container"] .stButton button *,
        div[data-testid="stElementContainer"]:has(.fc-pager-marker) + div[data-testid="stElementContainer"] .stButton button * {{
            color: {APPLE_INK} !important;
        }}
        div[data-testid="element-container"]:has(.fc-pager-marker) + div[data-testid="element-container"] .stButton button:disabled,
        div[data-testid="stElementContainer"]:has(.fc-pager-marker) + div[data-testid="stElementContainer"] .stButton button:disabled {{
            opacity: 0.35;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inject_card_css() -> None:
    """Styles render_player_card. Most of this styles elements the function
    fully owns (.fc-photo-wrap, .fc-stat-grid and children) — self-contained,
    no dependency on Streamlit's own generated markup. The one exception is
    the photo-click overlay block below, which does target Streamlit's
    internal data-testid structure (:has() + negative margin) to make the
    empty st.button right after the photo cover just the photo — see the
    docstring on render_player_card for why that one spot still needs it and
    how its blast radius is kept small."""
    inject_global_css()
    st.markdown(
        f"""
        <style>
        /* --- Card surface (grafica.md sez. 5): the native bordered
        container that wraps everything below, turned into the Apple-like
        white card.

        :has(.fc-photo-wrap) alone would match *every* ancestor
        stVerticalBlockBorderWrapper up to the page root (Streamlit gives
        that same testid to every block, not just border=True ones — only a
        generated, version-specific class tells them apart) — the photo is
        a descendant of all of them. Anchoring on the exact known DOM shape
        (wrapper > stVerticalBlock > element-container > ... > photo, via
        the child combinator on the first two hops) keeps this matching
        only the single innermost card wrapper. Dual selectors throughout
        for old ("element-container") vs new ("stElementContainer")
        Streamlit testid naming. */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] .fc-photo-wrap),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] .fc-photo-wrap) {{
            border-radius: 18px !important;
            border: 1px solid {APPLE_BORDER} !important;
            box-shadow: 0 2px 8px rgba(0,0,0,.04);
            background: #ffffff;
            overflow: hidden;
            transition: transform 180ms ease, box-shadow 180ms ease;
            padding: 0 !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] .fc-photo-wrap):hover,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] .fc-photo-wrap):hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(0,0,0,.08);
        }}
        /* Content below the photo gets the 20px padding instead (sez. 8),
        so the photo itself can still run edge-to-edge. Same depth-anchored
        scoping, then a plain > to only touch this card's own direct
        children (not some other card nested arbitrarily deep elsewhere). */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] .fc-photo-wrap) > div[data-testid="stVerticalBlock"] > div[data-testid="element-container"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] .fc-photo-wrap) > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] {{
            padding-left: 20px;
            padding-right: 20px;
        }}
        [data-testid="stElementContainer"]:has(.fc-photo-wrap),
        [data-testid="element-container"]:has(.fc-photo-wrap) {{
            padding: 0 !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] .fc-photo-wrap) > div[data-testid="stVerticalBlock"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] .fc-photo-wrap) > div[data-testid="stVerticalBlock"] {{
            gap: 0 !important;
        }}

        /* --- Photo (sez. 6) --- */
        .fc-photo-wrap {{
            position: relative;
            overflow: hidden;
        }}
        .fc-card-photo {{
            width: 100%;
            height: 190px;
            object-fit: cover;
            object-position: center 25%;
            display: block;
            border-radius: 17px;
        }}
        .fc-card-placeholder {{
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 48px;
            font-weight: bold;
        }}

        /* --- Rank badge (sez. 7): small circle, neutral by default, a very
        tenuous gold tint for the top 3 — never a dominant color. --- */
        .fc-card-rank {{
            position: absolute;
            top: 12px;
            left: 12px;
            width: 34px;
            height: 34px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: {APPLE_INK};
            font-size: 12px;
            font-weight: 700;
            background: rgba(255,255,255,.85);
            backdrop-filter: blur(4px);
        }}
        .fc-card-rank-gold {{
            background: rgba(255,204,0,.35);
            color: #7a5b00;
        }}

        /* --- Name / team (sez. 9-10) --- */
        .fc-card-name {{
            margin-top: 20px;
            font-size: 18px;
            font-weight: 600;
            line-height: 1.2;
            letter-spacing: -0.3px;
            color: {APPLE_INK};
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .fc-card-team {{
            margin-top: 4px;
            font-size: 13px;
            font-weight: 500;
            color: {APPLE_TERTIARY};
        }}
        .fc-card-extra {{
            margin-top: 4px;
            font-size: 11px;
            font-weight: 500;
            color: #b45309;
            height: 15px;
            line-height: 15px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        /* --- Rating (sez. 11): plain label/value stack, not a boxed
        metric — must visually dominate quotazione/FM. --- */
        .fc-rating {{
            margin-top: 18px;
        }}
        .fc-rating-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: .06em;
            color: {APPLE_TERTIARY};
        }}
        .fc-rating-value {{
            margin-top: 2px;
            font-size: 30px;
            font-weight: 600;
            letter-spacing: -1px;
            color: {APPLE_INK};
            font-variant-numeric: tabular-nums;
        }}

        /* --- Secondary stats grid (sez. 12-15) --- */
        .fc-stat-grid {{
            display: flex;
            background: {APPLE_SURFACE};
            border-radius: 12px;
            margin-top: 16px;
            padding: 12px 8px;
        }}
        .fc-stat-cell {{
            flex: 1;
            text-align: center;
            border-left: 1px solid {APPLE_BORDER};
        }}
        .fc-stat-cell:first-child {{
            border-left: none;
        }}
        .fc-stat-label {{
            font-size: 10px;
            font-weight: 600;
            color: {APPLE_TERTIARY};
            text-transform: uppercase;
        }}
        .fc-stat-value {{
            margin-top: 2px;
            font-size: 15px;
            font-weight: 600;
            color: {APPLE_INK};
            font-variant-numeric: tabular-nums;
        }}

        /* --- Photo click overlay: the real st.button right after
        .fc-photo-wrap is stretched invisibly over the photo. The one place
        in this file still coupled to Streamlit's internal data-testid
        structure (:has() + negative margin) since there is no native
        clickable-image widget — see render_player_card's docstring. --- */
        div[data-testid="element-container"]:has(.fc-photo-wrap) + div[data-testid="element-container"],
        div[data-testid="stElementContainer"]:has(.fc-photo-wrap) + div[data-testid="stElementContainer"] {{
            margin-top: -190px;
            position: relative;
            z-index: 10;
            padding: 0 !important;
        }}
        div[data-testid="element-container"]:has(.fc-photo-wrap) + div[data-testid="element-container"] button,
        div[data-testid="stElementContainer"]:has(.fc-photo-wrap) + div[data-testid="stElementContainer"] button {{
            height: 190px;
            width: 100% !important;
            opacity: 0;
            cursor: pointer;
            border: none;
            padding: 0;
            background: transparent;
        }}

        /* --- "Vedi scheda →" (sez. 16-17): a real st.button right after
        the .fc-link-marker span, restyled as plain accent-blue text, no
        button chrome. Micro hover animation nudges the arrow right. --- */
        div[data-testid="element-container"]:has(.fc-link-marker) + div[data-testid="element-container"] .stButton button,
        div[data-testid="stElementContainer"]:has(.fc-link-marker) + div[data-testid="stElementContainer"] .stButton button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {APPLE_ACCENT} !important;
            font-weight: 500;
            font-size: 14px;
            justify-content: flex-start;
            padding: 0 !important;
            margin-top: 20px;
            transition: transform 160ms ease;
        }}
        div[data-testid="element-container"]:has(.fc-link-marker) + div[data-testid="element-container"] .stButton button *,
        div[data-testid="stElementContainer"]:has(.fc-link-marker) + div[data-testid="stElementContainer"] .stButton button * {{
            color: {APPLE_ACCENT} !important;
        }}
        div[data-testid="element-container"]:has(.fc-link-marker) + div[data-testid="element-container"] .stButton button:hover,
        div[data-testid="stElementContainer"]:has(.fc-link-marker) + div[data-testid="stElementContainer"] .stButton button:hover {{
            transform: translateX(3px);
            background: transparent !important;
        }}

        /* --- Quantity control (sez. 18): the two st.button widgets right
        after .fc-qty-marker, unified into one pill — flush together, no
        individual borders, dark-gray (never blue) glyphs.

        st.columns(2) is a layout block, not an element-container, so its
        testid ("stHorizontalBlock") sits directly as the marker's next
        sibling — no intermediate element-container to select through, as
        confirmed by inspecting the live DOM. */
        div[data-testid="element-container"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] {{
            margin-top: 14px;
            margin-bottom: 20px;
            height: 40px;
            border: 1px solid {APPLE_BORDER};
            border-radius: 12px;
            background: {APPLE_SURFACE};
            overflow: hidden;
            gap: 0 !important;
        }}
        div[data-testid="element-container"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] .stButton button,
        div[data-testid="stElementContainer"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] .stButton button {{
            height: 40px;
            border-radius: 0 !important;
            border: none !important;
            background: transparent !important;
            color: {APPLE_GRAY} !important;
            font-size: 16px;
            font-weight: 600;
            box-shadow: none !important;
        }}
        div[data-testid="element-container"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] .stButton button *,
        div[data-testid="stElementContainer"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] .stButton button * {{
            color: {APPLE_GRAY} !important;
        }}
        div[data-testid="element-container"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] [data-testid="column"]:first-child .stButton button,
        div[data-testid="stElementContainer"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] [data-testid="column"]:first-child .stButton button {{
            border-right: 1px solid {APPLE_BORDER} !important;
        }}
        div[data-testid="element-container"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] .stButton button:active,
        div[data-testid="stElementContainer"]:has(.fc-qty-marker) + div[data-testid="stHorizontalBlock"] .stButton button:active {{
            transform: scale(0.96);
        }}

        /* Keep 4 cards per row down to fairly narrow windows: Streamlit's
        own column layout wraps/stacks once columns get too cramped, so we
        force nowrap and let cards shrink (rather than drop to 3/2 per row)
        until the true phone breakpoint below. Below that a 200px floor,
        cards scroll horizontally as a row instead of squeezing further
        (which was truncating names like "Carnesecchi M..."). */
        [data-testid="stHorizontalBlock"]:has(.fc-photo-wrap) {{
            gap: 20px;
            flex-wrap: nowrap !important;
            overflow-x: auto;
        }}
        /* flex-grow:0 (not 1): a trailing row with fewer than 4 cards
        (last page not an exact multiple of 4) must NOT stretch those cards
        wider than every other row's — basis is computed as if 4 siblings
        were always present, so a short last row just leaves empty space
        on the right instead of distorting its cards. */
        [data-testid="column"]:has(.fc-photo-wrap) {{
            min-width: 200px;
            flex: 0 1 calc((100% - 60px) / 4) !important;
        }}
        @media (max-width: 1199px) {{
            [data-testid="stHorizontalBlock"]:has(.fc-photo-wrap) {{
                gap: 16px;
            }}
            [data-testid="column"]:has(.fc-photo-wrap) {{
                flex: 0 1 calc((100% - 48px) / 4) !important;
            }}
        }}
        @media (max-width: 600px) {{
            [data-testid="stHorizontalBlock"]:has(.fc-photo-wrap) {{
                gap: 12px;
                flex-wrap: wrap !important;
            }}
            [data-testid="stHorizontalBlock"]:has(.fc-photo-wrap) > [data-testid="column"] {{
                flex: 0 1 calc(50% - 6px) !important;
                min-width: 150px;
            }}
            .fc-card-photo, .fc-card-placeholder {{
                height: 150px;
            }}
            div[data-testid="element-container"]:has(.fc-photo-wrap) + div[data-testid="element-container"] button,
            div[data-testid="stElementContainer"]:has(.fc-photo-wrap) + div[data-testid="stElementContainer"] button {{
                height: 150px;
            }}
            div[data-testid="element-container"]:has(.fc-photo-wrap) + div[data-testid="element-container"],
            div[data-testid="stElementContainer"]:has(.fc-photo-wrap) + div[data-testid="stElementContainer"] {{
                margin-top: -150px;
            }}
            .fc-card-name {{
                font-size: 16px;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )




