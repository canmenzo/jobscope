"""CSS + JS for the dashboard page, kept out of build_dashboard.py.

These are inlined verbatim into the generated HTML (no build step, no CDN), so
they are plain strings rather than f-strings — braces stay unescaped and the JS
below reads like JS. build_dashboard.py substitutes __TOKEN__ placeholders.

Layout: a dense sortable LIST on the left and a drag-and-drop KANBAN on the
right (Applied / Screening / Interview / Offer, plus a closed strip for
Accepted / Rejected / No response). A second top-level tab swaps the board for
the FLOW view — a full-width Sankey of how roles moved between stages.

Two colour systems, deliberately separated:
  * CHROME is the "neon cyber" skin — magenta edges and glows, near-black
    surfaces. It never encodes data. Raw magenta #c026d3 is 4.16:1 on the panel
    and is therefore used only for borders, rings and glows, never body text.
    Text steps run 16.4:1 / 11.1:1 / 6.5:1 / 4.0:1 so the dense list stays
    readable despite the dark skin.
  * DATA keeps the palette validated with the data-viz six checks: Applied ->
    Offer is an ORDINAL one-hue ramp (monotone lightness, adjacent dL >= 0.06);
    Accepted / Rejected are reserved STATUS colours, always drawn beside their
    name and count so hue never carries meaning alone.
"""

CSS = """
:root{
  /* chrome (neon skin) */
  --bg:#060609; --pane:#08080e; --panel:#0b0b14; --card:#101020; --field:#0c0c16;
  --edge:#1b1231; --edge-2:#2d1a4d; --edge-faint:#140e26;
  --neon:#c026d3; --neon-ink:#f0abfc; --cyan:#22d3ee; --cyan-ink:#67e8f9;
  /* text */
  --ink:#ece9f7; --ink-2:#c9bde8; --ink-3:#9b8dc4; --ink-4:#77699e;
  /* data */
  --st-applied:#1e4fa8; --st-screening:#2f6fdd; --st-interview:#4f8ef0;
  --st-offer:#7fb0f7; --st-accepted:#0ca30c; --st-rejected:#d03b3b;
  --st-ghosted:#6b7280; --st-none:#606b82;
  --money:#4ade80; --amber:#fbbf24;
  --num:ui-monospace,SFMono-Regular,Consolas,monospace;
  --r:8px; --r-lg:11px;
  /* One easing for everything that moves, so the whole page feels like one
     object rather than a pile of independently-animated widgets. */
  --ease:cubic-bezier(.4,0,.2,1);
  --spring:cubic-bezier(.34,1.4,.64,1);
}
@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes popIn{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:none}}
@keyframes countPop{0%{transform:scale(1)}40%{transform:scale(1.42);color:var(--neon-ink)}
                    100%{transform:scale(1)}}
@keyframes ringPulse{0%{box-shadow:0 0 0 0 #c026d366}70%{box-shadow:0 0 0 12px transparent}
                     100%{box-shadow:0 0 0 0 transparent}}
@keyframes shimmer{0%{background-position:-220% 0}100%{background-position:220% 0}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);
     color:var(--ink);overflow:hidden;font-size:13px}
.hidden{display:none !important}
button{font-family:inherit}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:var(--edge-2);border-radius:5px}
::-webkit-scrollbar-thumb:hover{background:#3d2266}
::-webkit-scrollbar-track{background:transparent}

.app{display:flex;flex-direction:column;height:100vh}

/* ---------------------------------------------------------------- top bar */
/* Tabs left, brand dead-centre, stats right. The brand is absolutely centred
   rather than flexed, so it stays on the page's midline no matter how wide the
   two side groups grow. The mark is the same reticle as the taskbar icon. */
.top{display:flex;align-items:center;gap:16px;padding:0 16px;height:52px;flex-shrink:0;
     background:var(--pane);border-bottom:1px solid var(--edge);position:relative;z-index:40;
     box-shadow:0 1px 0 #c026d333,0 8px 26px -16px #c026d355}
/* The wordmark used to stack two text-shadow glows under an 800 weight, which
   smears the letter edges and reads as pixelated at 14px. One soft drop-shadow
   on the whole mark renders far cleaner than glow baked into the glyphs, and
   the gradient fill carries the neon without touching legibility. */
.brand{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
       display:flex;align-items:center;gap:10px;text-decoration:none;
       color:var(--neon-ink);white-space:nowrap;
       filter:drop-shadow(0 0 9px #c026d34d);transition:filter .25s}
.brand:hover{filter:drop-shadow(0 0 14px #c026d380) brightness(1.08)}
.brand svg{width:20px;height:20px;flex-shrink:0;color:var(--neon)}
.brand span{font-size:15px;font-weight:700;letter-spacing:5.5px;text-transform:uppercase;
            background:linear-gradient(96deg,#f5c2fe 0%,#e879f9 48%,#67e8f9 100%);
            -webkit-background-clip:text;background-clip:text;color:transparent;
            -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
            text-rendering:optimizeLegibility;padding-right:5px}

.kpi{margin-left:auto;display:flex;gap:14px;font-size:11.5px;color:var(--ink-3);
     white-space:nowrap;z-index:1}
.kpi b{font-family:var(--num);color:var(--ink);font-size:13px}
.kpi i{font-style:normal;color:var(--ink-4);margin:0 1px}
.kpi .tot{color:var(--ink-3);font-size:12px}
.kpi span{cursor:default;transition:color .15s}
.kpi span:hover{color:var(--ink-2)}
.kpi .warn b{color:var(--amber)}
.kpi .kbtn{cursor:pointer}
.kpi .kbtn:hover b{color:var(--neon-ink);text-shadow:0 0 10px #c026d366}

.tabs{display:flex;gap:3px;padding:3px;background:var(--field);border:1px solid var(--edge-2);
      border-radius:var(--r);z-index:1}
.tab{padding:5px 15px;font-size:10.5px;font-weight:700;letter-spacing:1.4px;cursor:pointer;
     background:none;border:0;color:var(--ink-3);border-radius:5px;transition:.2s}
.tab:hover{color:var(--ink-2)}
.tab.on{background:#2a0733;color:var(--neon-ink);box-shadow:0 0 14px #c026d344,inset 0 0 12px #c026d322}

@media(max-width:1240px){ .brand span{display:none} }

.main{flex:1;display:flex;min-height:0}

/* ------------------------------------------------------------- left list */
/* The list claims the room that collapsed stages give up — that is the point
   of collapsing them. Width steps with how many stages are empty. */
.listpane.w1{width:59%}
.listpane.w2{width:65%}
.listpane.w3{width:71%}
.listpane{width:53%;min-width:420px;display:flex;flex-direction:column;min-height:0;
          background:var(--pane);border-right:1px solid var(--edge);transition:width .3s}
.listpane.dropping{box-shadow:inset 0 0 0 1px var(--neon),inset 0 0 40px #c026d31f}
.filters{display:flex;align-items:center;gap:6px;padding:9px 13px;flex-shrink:0;
         border-bottom:1px solid var(--edge);position:relative;z-index:30}
.search{flex:1;min-width:90px;height:30px;padding:0 11px;font-size:12.5px;color:var(--ink);
        background:var(--field);border:1px solid var(--edge-2);border-radius:var(--r);transition:.2s}
.search::placeholder{color:var(--ink-4)}
.search:focus{outline:0;border-color:var(--neon);box-shadow:0 0 0 3px #c026d322,0 0 18px #c026d344}
.fbtn{height:30px;padding:0 10px;font-size:11.5px;color:var(--ink-2);cursor:pointer;background:var(--field);
      border:1px solid var(--edge-2);border-radius:var(--r);display:flex;align-items:center;gap:5px;
      white-space:nowrap;transition:.18s}
.fbtn:hover{border-color:var(--neon);color:var(--ink)}
.fbtn.on{background:#2a0733;border-color:var(--neon);color:var(--neon-ink);box-shadow:0 0 12px #c026d344}
.fbtn .n{font-family:var(--num);font-size:10px;background:var(--neon);color:#fff;border-radius:8px;
         padding:0 5px;line-height:15px}
.car{opacity:.5;font-size:9px}

.fdd{position:relative}
.fddmenu{position:absolute;top:calc(100% + 6px);left:0;width:262px;z-index:50;padding:8px;
         background:#0a0a13;border:1px solid var(--edge-2);border-radius:var(--r-lg);
         box-shadow:0 18px 44px #000c,0 0 0 1px #c026d322,0 0 30px #c026d31f;
         animation:pop .16s ease-out}
@keyframes pop{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:none}}
.fddmenu.right{left:auto;right:0}
.fddsearch{width:100%;height:29px;padding:0 9px;margin-bottom:7px;font-size:12px;color:var(--ink);
           background:var(--field);border:1px solid var(--edge-2);border-radius:6px}
.fddsearch:focus{outline:0;border-color:var(--neon)}
.fddlist{max-height:300px;overflow-y:auto;display:flex;flex-direction:column;gap:1px}
.fddgrp{font-size:9px;letter-spacing:1.2px;color:var(--ink-4);text-transform:uppercase;
        padding:8px 7px 3px;font-weight:700}
.fddopt{display:flex;align-items:center;gap:8px;padding:6px 7px;border-radius:6px;font-size:12.5px;
        color:var(--ink-2);cursor:pointer;transition:.12s}
.fddopt:hover{background:#1a0f2b;color:var(--ink)}
.fddopt input{accent-color:var(--neon);margin:0;cursor:pointer}
.fddopt .fct{margin-left:auto;font-family:var(--num);color:var(--ink-4);font-size:11px}
.fddopt.zero{opacity:.4}
.sw{width:8px;height:8px;border-radius:2px;flex-shrink:0}
.fddfoot{display:flex;justify-content:space-between;margin-top:7px;padding-top:7px;
         border-top:1px solid var(--edge)}
.fddfoot button{background:0;border:0;color:var(--cyan-ink);font-size:11px;cursor:pointer;padding:2px}
.fddfoot button:hover{text-shadow:0 0 8px currentColor}
.fddempty{color:var(--ink-4);font-size:12px;padding:9px 7px}

.lhead{display:grid;grid-template-columns:42px 1fr 120px 92px 42px 82px;gap:9px;padding:7px 13px;
       font-size:9px;letter-spacing:1.2px;color:var(--ink-4);text-transform:uppercase;font-weight:700;
       border-bottom:1px solid var(--edge);flex-shrink:0;user-select:none}
.lhead span{cursor:pointer;transition:.15s}
.lhead span:hover{color:var(--cyan-ink)}
.lhead span.sorted{color:var(--neon-ink)}
.rows{flex:1;overflow-y:auto}
.row{display:grid;grid-template-columns:42px 1fr 120px 92px 42px 82px;gap:9px;padding:8px 13px;
     align-items:center;cursor:grab;position:relative;border-bottom:1px solid var(--edge-faint);
     transition:background .14s}
.row:hover{background:#12091f;box-shadow:inset 0 0 26px #c026d312}
.row::before{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:var(--neon);
             box-shadow:0 0 10px var(--neon);transform:scaleY(0);transition:transform .18s}
.row:hover::before{transform:scaleY(1)}
.row.dragging{opacity:.35}
.row.tracked{background:#0d1220}
.row.tracked .rt{color:var(--ink-2)}
.sc{font-family:var(--num);font-size:12px;font-weight:700;text-align:center;padding:2px 0;
    border-radius:5px;color:var(--cyan-ink);background:#03181f;border:1px solid #0e5c72;
    box-shadow:0 0 10px #67e8f92b,inset 0 0 8px #67e8f912}
/* Fit band, so reachability is visible in the list instead of hidden in a
   tooltip. Green you clear comfortably, amber is a stretch, red is a reach.
   The number stays the number — the band only tints its frame. */
.sc.safe{color:#4ade80;background:#04180d;border-color:#1f6b3a;
         box-shadow:0 0 10px #4ade8026,inset 0 0 8px #4ade8010}
.sc.target{color:#fbbf24;background:#1a1204;border-color:#6b5119;
           box-shadow:0 0 10px #fbbf2426,inset 0 0 8px #fbbf2410}
.sc.reach{color:#f87171;background:#1a0707;border-color:#6b2020;
          box-shadow:0 0 10px #f8717126,inset 0 0 8px #f8717110}
.row:hover .sc.safe{box-shadow:0 0 14px #4ade8047}
.row:hover .sc.target{box-shadow:0 0 14px #fbbf2447}
.row:hover .sc.reach{box-shadow:0 0 14px #f8717147}
.rt{font-size:12.5px;font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;
    text-overflow:ellipsis}
.rt a{color:inherit;text-decoration:none}
.rt a:hover{color:var(--neon-ink);text-shadow:0 0 10px #c026d366}
.rc,.rl{font-size:11.5px;color:var(--ink-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ra{font-family:var(--num);font-size:11px;color:var(--ink-4);text-align:right}
.ra.stale{color:var(--amber)}
.rs{font-family:var(--num);font-size:10.5px;color:var(--money);text-align:right;white-space:nowrap}
.tag{font-size:8px;letter-spacing:.6px;font-weight:700;padding:1px 5px;border-radius:6px;
     margin-left:6px;vertical-align:1px}
.tag.ghost{background:#2a1004;color:#fb923c}
.tag.new{background:#04230f;color:#22ff9c}
.tag.loc{background:#0d1b2e;color:#7fb0f7}
.tag.nospon{background:#2a0a0a;color:#f87171}
.tag.spon{background:#04220f;color:#4ade80}
.stagedot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-left:6px;
          vertical-align:1px;box-shadow:0 0 7px currentColor}
.racts{position:absolute;right:9px;top:50%;transform:translateY(-50%);display:none;gap:4px;
       background:linear-gradient(90deg,transparent,#12091f 22%);padding-left:26px}
.row:hover .racts{display:flex}
.iact{width:25px;height:25px;display:grid;place-items:center;font-size:12px;cursor:pointer;
      background:var(--card);border:1px solid var(--edge-2);border-radius:6px;color:var(--ink-2);
      transition:.16s}
.iact:hover{border-color:var(--neon);color:var(--neon-ink);box-shadow:0 0 12px #c026d355}

/* ----------------------------------------------------------- right board */
.right{flex:1;display:flex;flex-direction:column;min-height:0;background:var(--bg)}
.board{flex:1;display:flex;flex-direction:column;min-height:0;padding:11px 13px;gap:9px}
.board .closed{order:-1}
.cols{flex:1;display:flex;gap:9px;min-height:0}
.col{flex:1 1 0;min-width:0;display:flex;flex-direction:column;min-height:0;
     border-radius:var(--r-lg);background:var(--panel);border:1px solid var(--edge);
     transition:flex-basis .28s cubic-bezier(.4,0,.2,1),flex-grow .28s,border-color .2s,background .2s;
     position:relative}
.col.over{border-color:var(--neon);background:#140828;box-shadow:0 0 0 1px var(--neon),0 0 30px #c026d344}
/* An empty stage collapses to a vertical rail so the list gets the room; it
   springs open when a card is dragged over it, and stays open once filled. */
.col.rail{flex:0 0 34px;cursor:pointer}
.col.rail .cb,.col.rail .ch .cn,.col.rail .ch .sw{display:none}
.col.rail .ch{writing-mode:vertical-rl;transform:rotate(180deg);height:100%;justify-content:flex-end;
              padding:10px 8px;border:0;gap:9px;letter-spacing:1.6px}
.col.rail .ch::after{content:'\\25B8';transform:rotate(90deg);opacity:.45;font-size:11px}
.col.rail:hover{border-color:var(--edge-2)}
.col.rail:hover .ch{color:var(--ink-2)}
.col.rail.over{flex:1 1 0}
.col.rail.over .cb{display:flex}
.col.rail.over .ch{writing-mode:horizontal-tb;transform:none;height:auto;
                   border-bottom:1px solid var(--edge-faint);letter-spacing:1.2px}
.col.rail.over .ch::after{display:none}
.col.rail.over .ch .cn,.col.rail.over .ch .sw{display:block}
.ch{display:flex;align-items:center;gap:6px;padding:9px 10px;flex-shrink:0;font-size:9px;
    letter-spacing:1.2px;text-transform:uppercase;font-weight:700;color:var(--ink-3);
    border-bottom:1px solid var(--edge-faint)}
.ch .cn{margin-left:auto;font-family:var(--num);font-size:11px;color:var(--ink);letter-spacing:0}
.cb{flex:1;overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:7px}
.kc{padding:9px 10px;border-radius:var(--r);background:var(--card);border:1px solid var(--edge-2);
    cursor:grab;position:relative;overflow:hidden;animation:rise .3s both;
    transition:transform .18s,box-shadow .18s,border-color .18s}
.kc:hover{transform:translateY(-2px);border-color:var(--neon);
          box-shadow:0 0 20px #c026d344,0 0 0 1px #f0abfc55}
.kc::after{content:'';position:absolute;inset:0;pointer-events:none;
           background:linear-gradient(115deg,transparent 38%,#f0abfc26 50%,transparent 62%);
           transform:translateX(-130%);transition:transform .65s}
.kc:hover::after{transform:translateX(130%)}
.kc.dragging{opacity:.35}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.kc .kt{display:block;font-size:11.5px;font-weight:600;line-height:1.32;color:var(--ink);
        margin-bottom:2px;padding-right:18px;text-decoration:none;transition:color .15s}
.kc .kt:hover{color:var(--neon-ink);text-shadow:0 0 10px #c026d366}
.kc .kt::after{content:'97';opacity:0;margin-left:5px;font-size:10px;transition:opacity .15s}
.kc:hover .kt::after{opacity:.55}
.kc .kco{font-size:10.5px;color:var(--ink-3)}
.kmeta{display:flex;align-items:center;gap:5px;margin-top:6px;font-size:9.5px;color:var(--ink-4);
       font-family:var(--num);flex-wrap:wrap}
.kmeta .ks{margin-left:auto;color:var(--money)}
.kx{position:absolute;top:6px;right:6px;width:17px;height:17px;display:none;place-items:center;
    font-size:11px;line-height:1;background:var(--field);border:1px solid var(--edge-2);
    border-radius:5px;color:var(--ink-4);cursor:pointer;z-index:2}
.kc:hover .kx{display:grid}
.kx:hover{color:#ff8080;border-color:#5c2b2b}
.knote{width:100%;margin-top:7px;padding:6px 7px;font-size:11px;font-family:inherit;color:var(--ink-2);
       background:var(--field);border:1px solid var(--edge-2);border-radius:6px;resize:vertical;
       min-height:44px}
.knote:focus{outline:0;border-color:var(--neon)}
.kc .nbadge{color:var(--amber)}
.slot{border:1px dashed var(--edge-2);border-radius:var(--r);padding:18px 10px;text-align:center;
      font-size:10.5px;color:var(--ink-4);line-height:1.5}

.closed{flex-shrink:0;display:flex;align-items:center;gap:7px;padding:7px 11px;border-radius:var(--r-lg);
        background:var(--panel);border:1px dashed var(--edge-2);font-size:10.5px;color:var(--ink-3)}
.closed .lab{font-size:9px;letter-spacing:1.2px;text-transform:uppercase;font-weight:700;
             color:var(--ink-4);margin-right:2px}
.cl{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:20px;background:var(--field);
    border:1px solid var(--edge-2);cursor:pointer;transition:.18s;white-space:nowrap}
.cl:hover{border-color:var(--neon);box-shadow:0 0 14px #c026d344}
.cl.over{border-color:var(--neon);background:#2a0733;box-shadow:0 0 18px #c026d366}
.cl b{font-family:var(--num);color:var(--ink)}
.cl .sw{border-radius:50%}
.hint{margin-left:auto;color:var(--ink-4);font-size:10px;white-space:nowrap;overflow:hidden}
.listpane.w2 ~ .right .hint,.listpane.w3 ~ .right .hint{display:none}

/* ------------------------------------------------------------- flow view */
.flow{flex:1;display:flex;flex-direction:column;min-height:0;padding:16px 22px 20px;gap:14px;
      overflow-y:auto}
.funnel{display:flex;gap:9px;flex-wrap:wrap;flex-shrink:0}
.fstat{flex:1;min-width:128px;padding:11px 13px;border-radius:var(--r-lg);background:var(--panel);
       border:1px solid var(--edge);position:relative;overflow:hidden}
.fstat::before{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:var(--bar)}
.fstat .fv{font-family:var(--num);font-size:23px;font-weight:700;color:var(--ink);line-height:1.1}
.fstat .fl{font-size:10px;letter-spacing:1.1px;text-transform:uppercase;color:var(--ink-3);
           margin-top:3px;font-weight:700}
.fstat .fr{font-size:10.5px;color:var(--ink-4);margin-top:4px;font-family:var(--num)}
.flowbox{flex:1;min-height:260px;border-radius:var(--r-lg);background:var(--panel);
         border:1px solid var(--edge);padding:14px 16px;display:flex;flex-direction:column}
.flowbox h2{margin:0 0 2px;font-size:10px;letter-spacing:1.4px;text-transform:uppercase;
            color:var(--ink-3);font-weight:700}
.flowhead{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}
.flowhead .tbtn{padding:5px 11px;font-size:11.5px}
.flowhead .acts{margin-left:auto;display:flex;gap:6px}
.flowbox .sub{font-size:11px;color:var(--ink-4);margin-bottom:8px}
#sankey{width:100%;flex:1;display:block}
.sk-lab,.sk-val{paint-order:stroke fill;stroke:var(--panel);stroke-width:3.5px;stroke-linejoin:round}
.sk-lab{font-size:11.5px;fill:var(--ink-2)}
.sk-val{font-size:12px;fill:var(--ink);font-weight:700;font-family:var(--num)}
.sk-flow{transition:opacity .14s}
.flowbox.dim .sk-flow{opacity:.13}
.sk-flow.hot{opacity:.9 !important}
.sk-node{transition:filter .14s}
.sk-node:hover{filter:brightness(1.3)}
.flow-empty{color:var(--ink-3);font-size:13px;line-height:1.7;padding:30px 4px;text-align:center}
.flow-empty b{color:var(--neon-ink)}

.foot{flex-shrink:0;display:flex;align-items:center;gap:8px;height:26px;padding:0 16px;
      font-size:10.5px;color:var(--ink-4);background:var(--pane);
      border-top:1px solid var(--edge)}
.foot b{font-family:var(--num);color:var(--ink-3);font-weight:400}

/* ------------------------------------------------------- companies sheet */
/* Opened from the "companies" stat. Every company the run searched, so the
   empty ones are visible too — coverage is the question this answers. */
.ov{position:fixed;inset:0;z-index:80;display:flex;align-items:center;justify-content:center;
    padding:38px 24px;background:#03030799;backdrop-filter:blur(3px);
    animation:fadeUp .16s var(--ease) both}
.ovbox{width:min(1000px,100%);max-height:100%;display:flex;flex-direction:column;
       background:var(--panel);border:1px solid var(--edge-2);border-radius:var(--r-lg);
       box-shadow:0 30px 80px #000d,0 0 0 1px #c026d322,0 0 44px #c026d326;
       animation:menuIn .2s var(--spring) both}
.ovhead{display:flex;align-items:center;gap:12px;padding:12px 15px;flex-shrink:0;
        border-bottom:1px solid var(--edge)}
.ovhead h2{margin:0;font-size:11px;letter-spacing:1.6px;text-transform:uppercase;
           color:var(--neon-ink);font-weight:700}
.ovsub{font-size:11.5px;color:var(--ink-4)}
.ovsearch{margin-left:auto;width:230px;height:29px;padding:0 10px;font-size:12.5px;color:var(--ink);
          background:var(--field);border:1px solid var(--edge-2);border-radius:var(--r)}
.ovsearch::placeholder{color:var(--ink-4)}
.ovsearch:focus{outline:0;border-color:var(--neon);box-shadow:0 0 0 3px #c026d322}
.ovx{width:29px;height:29px;display:grid;place-items:center;font-size:17px;line-height:1;cursor:pointer;
     background:var(--field);border:1px solid var(--edge-2);border-radius:var(--r);color:var(--ink-3)}
.ovx:hover{border-color:var(--neon);color:var(--neon-ink)}
.ovbody{overflow-y:auto;padding:12px 15px 16px}
.cgrp{font-size:9px;letter-spacing:1.2px;text-transform:uppercase;color:var(--ink-4);
      font-weight:700;margin:14px 2px 7px}
.cgrp:first-child{margin-top:0}
.cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(212px,1fr));gap:7px}
.ccard{display:flex;align-items:center;gap:8px;padding:9px 10px;border-radius:var(--r);
       background:var(--card);border:1px solid var(--edge);cursor:pointer;
       transition:transform .16s var(--spring),border-color .16s,box-shadow .16s}
.ccard:hover{transform:translateY(-2px);border-color:var(--neon);box-shadow:0 0 18px #c026d33d}
.ccard.dim{opacity:.55;cursor:default}
.ccard.dim:hover{transform:none;border-color:var(--edge);box-shadow:none}
.cinfo{flex:1;min-width:0}
.cname{font-size:12.5px;font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;
       text-overflow:ellipsis}
.cmeta{font-size:10px;color:var(--ink-4);margin-top:2px;font-family:var(--num);
       white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cmeta.err{color:#f87171}
.ccount{font-family:var(--num);font-size:12px;font-weight:700;padding:2px 7px;border-radius:5px;
        color:var(--cyan-ink);background:#03181f;border:1px solid #0e5c72}
.ccard.dim .ccount{color:var(--ink-4);background:var(--field);border-color:var(--edge-2)}
.cgo{color:var(--ink-4);text-decoration:none;font-size:12px;padding:2px 3px}
.cgo:hover{color:var(--neon-ink);text-shadow:0 0 10px #c026d366}

.tip{position:fixed;z-index:90;max-width:330px;padding:9px 12px;font-size:12px;line-height:1.55;
     color:var(--ink-2);background:#0a0a13;border:1px solid var(--edge-2);border-radius:9px;
     pointer-events:none;box-shadow:0 12px 34px #000d,0 0 22px #c026d333;
     animation:fadeUp .13s var(--ease) both}
.tip b{color:var(--ink)}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:95;display:flex;
       align-items:center;gap:12px;padding:10px 16px;font-size:12.5px;color:var(--ink);
       background:#0d0a18;border:1px solid var(--neon);border-radius:24px;
       box-shadow:0 0 26px #c026d355,0 12px 34px #000c;animation:pop .18s}
.toast button{background:0;border:0;color:var(--cyan-ink);font-size:12px;cursor:pointer;font-weight:700}
.empty-list{padding:40px 20px;text-align:center;color:var(--ink-4);font-size:12.5px}

/* ---------------------------------------------------------------- polish */
/* Everything below is motion and depth only — no layout depends on it, and
   the reduced-motion block at the end switches all of it off. */

.app{animation:fadeUp .34s var(--ease) both}

/* Buttons: lift + bloom on hover, real press on click. */
.fbtn,.tab,.cl,.iact{position:relative;will-change:transform}
.fbtn{transition:transform .16s var(--spring),border-color .18s,color .18s,
      background .18s,box-shadow .18s}
.fbtn:hover{transform:translateY(-1px);box-shadow:0 4px 14px #c026d326}
.fbtn:active{transform:translateY(1px) scale(.98);transition-duration:.06s}
.fbtn.on{animation:ringPulse .5s var(--ease)}
.fbtn .n{transition:transform .18s var(--spring)}
.fbtn:hover .n{transform:scale(1.1)}
.tab{transition:color .18s,background .24s var(--ease),box-shadow .24s}
.tab:active{transform:scale(.97)}
.iact{transition:transform .16s var(--spring),border-color .16s,color .16s,box-shadow .16s}
.iact:hover{transform:translateY(-1px) scale(1.06)}
.iact:active{transform:scale(.92);transition-duration:.06s}
.cl{transition:transform .16s var(--spring),border-color .18s,box-shadow .18s,background .18s}
.cl:hover{transform:translateY(-1px)}

/* Rows fade in on first paint, staggered by index (set in JS). */
.row{animation:fadeUp .3s var(--ease) both;animation-delay:var(--d,0ms)}
.row .sc{transition:transform .16s var(--spring),box-shadow .18s}
.row:hover .sc{transform:scale(1.07);box-shadow:0 0 14px #67e8f947}
.row:active{cursor:grabbing}
.row.dragging{transform:scale(.99) rotate(-.4deg)}

/* Kanban: the column you are about to drop on breathes. */
.col{will-change:flex-basis}
.col.over{animation:ringPulse .6s var(--ease) infinite}
.col.over .cb{transform:scale(1.005)}
.cb{transition:transform .2s var(--ease)}
.kc{will-change:transform}
.kc:active{cursor:grabbing;transform:scale(.985) rotate(-.5deg)}
.kc.dragging{transform:scale(.97) rotate(-1.2deg)}
.ch .cn{display:inline-block}
.ch .cn.bump{animation:countPop .42s var(--spring)}
.cl b.bump{display:inline-block;animation:countPop .42s var(--spring)}
.slot{transition:border-color .2s,color .2s,background .2s}
.col.over .slot{border-color:var(--neon);color:var(--neon-ink);background:#1a0b2e}

/* Tabs crossfade their panes instead of hard-swapping. */
#viewBoard,#viewFlow{animation:fadeUp .26s var(--ease) both}
.listpane{transition:opacity .22s var(--ease),width .3s var(--ease)}

/* Flow view */
.fstat{animation:fadeUp .34s var(--ease) both;animation-delay:var(--d,0ms);
       transition:transform .18s var(--spring),border-color .18s,box-shadow .18s}
.fstat:hover{transform:translateY(-2px);border-color:var(--edge-2);
             box-shadow:0 8px 22px #0009,0 0 18px #c026d31f}
.fstat::after{content:'';position:absolute;inset:0;pointer-events:none;border-radius:inherit;
  background:linear-gradient(100deg,transparent 40%,#f0abfc14 50%,transparent 60%);
  background-size:220% 100%;animation:shimmer 5.5s linear infinite}
.sk-node,.sk-flow{transition:opacity .16s,filter .16s}

/* Toast slides up from the edge. */
.toast{animation:toastIn .28s var(--spring) both}
@keyframes toastIn{from{opacity:0;transform:translate(-50%,16px) scale(.96)}
                   to{opacity:1;transform:translate(-50%,0) scale(1)}}
.toast button{transition:transform .14s var(--spring),text-shadow .18s}
.toast button:hover{transform:scale(1.08);text-shadow:0 0 10px currentColor}

/* Menus grow from their button rather than appearing. */
.fddmenu{transform-origin:top left;animation:menuIn .18s var(--spring) both}
.fddmenu.right{transform-origin:top right}
@keyframes menuIn{from{opacity:0;transform:translateY(-6px) scale(.97)}
                  to{opacity:1;transform:none}}
.fddopt{transition:background .13s,color .13s,padding-left .13s}
.fddopt:hover{padding-left:10px}

.rows{scroll-behavior:smooth}

@media (prefers-reduced-motion: reduce){
  *,*::before,*::after{animation-duration:.001ms !important;animation-iteration-count:1 !important;
                       transition-duration:.001ms !important;scroll-behavior:auto !important}
}
@media(max-width:1180px){
  .listpane{width:46%;min-width:360px}
  .cols{grid-template-columns:repeat(2,minmax(0,1fr))}
}
"""


JS = """
const JOBS = __JOBS__;
const STAGES = __STAGES__;
const BOARD_STAGES = __BOARD_STAGES__;
const CLOSED_STAGES = __CLOSED_STAGES__;
const FACET_DEFS = __FACET_DEFS__;
const FACET_META = __FACET_META__;   // {field: {order:[], labels:{}}}
const PRIMARY_FACETS = __PRIMARY_FACETS__;
const STALE_BUCKETS = __STALE_BUCKETS__;
const COMPANIES = __COMPANY_DATA__;  // every company searched, matched or not

const LSKEY = 'jobscope.apps', VIEWKEY = 'jobscope.view';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const rows = $$('.row'), rows_ = rows;
const q = $('#q'), rowsEl = $('#rows'), tip = $('#tip');

let APPS = Object.assign({}, __APPS__, JSON.parse(localStorage.getItem(LSKEY) || '{}'));
const facets = {};
FACET_DEFS.forEach(([f]) => facets[f] = new Set());
let newOnly = false, freshOnly = true, hideGhosts = false;
// The forward order of the funnel. Anything not on it (Rejected, No response)
// is terminal and always appends rather than trimming.
const FUNNEL = ['none'].concat(BOARD_STAGES, ['accepted']);
let sortKey = 'score', sortDir = -1, undoState = null, toastTimer = null;

const stage = id => (APPS[id] || {}).status || 'none';
const meta = k => STAGES.find(s => s[0] === k) || ['none', 'Not applied', '--st-none'];
const label = k => meta(k)[1];
const cvar = k => meta(k)[2];
const saveApps = () => localStorage.setItem(LSKEY, JSON.stringify(APPS));

/* ------------------------------------------------------------------ state */

// History used to be append-only, so a role dragged out of Screening kept
// "reached Screening" forever. New moves trim correctly now, but entries
// already in localStorage still carry the stale stage — and that is what the
// Flow view draws. Reconcile every entry against its CURRENT status on load:
// a role sitting at Applied cannot have reached anything later, and cannot
// also have been Rejected. Terminal statuses keep their whole path, because
// that path really did happen.
function repairHistory() {
  let fixed = 0;
  Object.values(APPS).forEach(e => {
    if (!e || !Array.isArray(e.history)) return;
    const cur = FUNNEL.indexOf(e.status || 'none');
    if (cur === -1) return;                    // rejected / ghosted / accepted
    const before = e.history.length;
    e.history = e.history.filter(h => {
      const i = FUNNEL.indexOf(h.stage);
      return i !== -1 && i <= cur;
    });
    if (e.history.length !== before) fixed++;
  });
  if (fixed) saveApps();
  return fixed;
}

function setStage(id, next, record) {
  const prev = stage(id);
  if (prev === next) return;
  let e = APPS[id];
  if (!e) e = APPS[id] = { history: [] };
  if (!e.history) e.history = [];
  e.status = next;
  if (record) {
    const today = new Date().toISOString().slice(0, 10);
    const at = s => FUNNEL.indexOf(s);
    // Moving BACKWARDS along the funnel is a correction, not progress: trim the
    // stages you undid instead of appending. Otherwise dragging a card out of
    // Screening leaves "reached Screening" in the history forever and the Flow
    // view keeps showing a stage that is now empty.
    if (at(next) !== -1 && at(prev) !== -1 && at(next) < at(prev)) {
      e.history = e.history.filter(h => at(h.stage) !== -1 && at(h.stage) <= at(next));
      if (next === 'none') e.history = [];
    } else {
      if (!e.history.length && prev !== 'none') e.history.push({ stage: prev, date: today });
      if (next !== 'none') e.history.push({ stage: next, date: today });
    }
    if (next === 'applied' && !e.applied_date) e.applied_date = today;
  }
  const j = JOBS[id] || {};
  e.title = j.title; e.company = j.comp; e.url = j.url;
  if (next === 'none' && !(e.note || '').trim()) delete APPS[id];
  saveApps();
}

function move(id, next) {
  const prev = stage(id);
  setStage(id, next, true);
  undoState = { id, prev };
  render();
  toast(`${JOBS[id].title} \\u2192 ${label(next)}`, () => {
    setStage(id, undoState.prev, false);
    const e = APPS[id]; if (e && e.history) e.history.pop();
    saveApps(); render();
  });
}

function toast(msg, undo) {
  $('#toast')?.remove();
  clearTimeout(toastTimer);
  const t = document.createElement('div');
  t.className = 'toast'; t.id = 'toast';
  t.innerHTML = `<span>${msg}</span>`;
  if (undo) {
    const b = document.createElement('button');
    b.textContent = 'Undo';
    b.onclick = () => { undo(); t.remove(); };
    t.appendChild(b);
  }
  document.body.appendChild(t);
  toastTimer = setTimeout(() => t.remove(), 4200);
}

/* ----------------------------------------------------------------- filter */

function vals(row, f) {
  if (f === 'state') return row.dataset.state.split(' ').filter(Boolean);
  if (f === 'status') return [stage(row.dataset.id)];
  return [row.dataset[f]];
}

function passes(row, skip) {
  // The list is the queue of roles still to triage, so anything you have moved
  // onto the board leaves it. Selecting its stage in the Stage filter brings it
  // back — that is the one way to see what you have already applied to.
  if (skip !== 'status') {
    const st = stage(row.dataset.id);
    if (st !== 'none' && !facets.status.has(st)) return false;
  }
  const term = q.value.trim().toLowerCase();
  if (term && !row.dataset.search.includes(term)) return false;
  if (newOnly && row.dataset.new !== '1') return false;
  if (hideGhosts && row.dataset.ghost === '1') return false;
  if (freshOnly && STALE_BUCKETS.includes(row.dataset.age)) return false;
  for (const f in facets) {
    if (f === skip || !facets[f].size) continue;
    if (!vals(row, f).some(v => facets[f].has(v))) return false;
  }
  return true;
}

/* -------------------------------------------------------------- dropdowns */

function optionsFor(field) {
  const counts = new Map();
  rows.forEach(r => {
    if (!passes(r, field)) return;
    vals(r, field).forEach(v => counts.set(v, (counts.get(v) || 0) + 1));
  });
  facets[field].forEach(v => { if (!counts.has(v)) counts.set(v, 0); });
  // Metadata comes from one global table, NOT from a [data-facet] element:
  // the facets inside "More" have no element of their own, and looking them
  // up in the DOM returned null and threw, silently emptying that whole menu.
  const m = FACET_META[field] || {};
  const order = m.order || [], labels = m.labels || {};
  return [...counts.keys()].sort((a, b) => {
    const ia = order.indexOf(a), ib = order.indexOf(b);
    if (ia !== -1 || ib !== -1) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    return counts.get(b) - counts.get(a) || String(a).localeCompare(String(b));
  }).map(v => ({ v, label: labels[v] || v, n: counts.get(v) }));
}

function renderMenu(dd, field) {
  const term = (dd.querySelector('.fddsearch').value || '').trim().toLowerCase();
  const list = dd.querySelector('.fddlist');
  const fields = field ? [field] : JSON.parse(dd.dataset.fields || '[]');
  let out = '';
  fields.forEach(f => {
    const opts = optionsFor(f).filter(o => !term || o.label.toLowerCase().includes(term));
    if (!opts.length) return;
    if (fields.length > 1) {
      const def = FACET_DEFS.find(d => d[0] === f);
      out += `<div class="fddgrp">${def ? def[1] : f}</div>`;
    }
    out += opts.map(o => {
      const on = facets[f].has(o.v);
      const sw = f === 'status'
        ? `<span class="sw" style="background:var(${cvar(o.v)})"></span>` : '';
      return `<label class="fddopt${o.n ? '' : ' zero'}" data-f="${f}">`
        + `<input type="checkbox" value="${o.v}"${on ? ' checked' : ''}>${sw}`
        + `<span>${o.label}</span><span class="fct">${o.n}</span></label>`;
    }).join('');
  });
  list.innerHTML = out || '<div class="fddempty">No match.</div>';
}

function closeMenus(except) {
  $$('.fddmenu').forEach(m => { if (m.parentElement !== except) m.remove(); });
  $$('.fdd .fbtn').forEach(b => b.classList.remove('menu-open'));
}

function wireDropdown(dd) {
  const single = dd.dataset.facet, fields = JSON.parse(dd.dataset.fields || '[]');
  dd.querySelector('.fbtn').addEventListener('click', e => {
    e.stopPropagation();
    const open = dd.querySelector('.fddmenu');
    closeMenus();
    if (open) return;
    const m = document.createElement('div');
    m.className = 'fddmenu' + (dd.dataset.align === 'right' ? ' right' : '');
    m.innerHTML = `<input class="fddsearch" placeholder="Search\\u2026" autocomplete="off">`
      + `<div class="fddlist"></div><div class="fddfoot">`
      + `<button class="fdd-all">Select all</button><button class="fdd-none">Clear</button></div>`;
    dd.appendChild(m);
    m.addEventListener('click', ev => ev.stopPropagation());
    m.querySelector('.fddsearch').addEventListener('input', () => renderMenu(dd, single));
    m.querySelector('.fddlist').addEventListener('change', ev => {
      const cb = ev.target.closest('input'); if (!cb) return;
      const f = cb.closest('.fddopt').dataset.f;
      cb.checked ? facets[f].add(cb.value) : facets[f].delete(cb.value);
      render(); renderMenu(dd, single);
    });
    m.querySelector('.fdd-all').addEventListener('click', () => {
      (single ? [single] : fields).forEach(f =>
        optionsFor(f).forEach(o => { if (o.n) facets[f].add(o.v); }));
      render(); renderMenu(dd, single);
    });
    m.querySelector('.fdd-none').addEventListener('click', () => {
      (single ? [single] : fields).forEach(f => facets[f].clear());
      render(); renderMenu(dd, single);
    });
    renderMenu(dd, single);
    m.querySelector('.fddsearch').focus();
  });
}
$$('.fdd').forEach(wireDropdown);
document.addEventListener('click', () => closeMenus());

/* --------------------------------------------------------------- the list */

function sortRows() {
  const get = (r) => {
    if (sortKey === 'score') return +r.dataset.score;
    if (sortKey === 'age') return +r.dataset.days;
    if (sortKey === 'salary') return +r.dataset.salnum;
    return null;
  };
  rows.slice().sort((a, b) => {
    if (sortKey === 'title' || sortKey === 'company' || sortKey === 'location') {
      const k = sortKey === 'company' ? 'comp' : sortKey === 'location' ? 'loc' : 'ttl';
      return a.dataset[k].localeCompare(b.dataset[k]) * sortDir;
    }
    return (get(a) - get(b)) * sortDir || a.dataset.comp.localeCompare(b.dataset.comp);
  }).forEach(r => rowsEl.appendChild(r));
}

/* ---------------------------------------------------------------- kanban */

// Write a number and, if it actually changed, flash it so the eye follows the
// card that just moved instead of hunting for which column ticked.
function bump(el, value) {
  if (!el) return;
  const next = String(value);
  if (el.textContent === next) return;
  el.textContent = next;
  el.classList.remove('bump');
  void el.offsetWidth;              // restart the animation
  el.classList.add('bump');
}

function kcard(id) {
  const j = JOBS[id], e = APPS[id] || {};
  const note = (e.note || '').trim();
  const div = document.createElement('div');
  div.className = 'kc'; div.draggable = true; div.dataset.id = id;
  // The title is the way to the posting — a card you have parked in Applied is
  // exactly the thing you come back to apply to. draggable="false" on the
  // anchor matters: without it the browser hijacks the card's drag with its own
  // link-drag, and the card can no longer be moved by grabbing its title.
  div.innerHTML = `<button class="kx" data-tip="Back to Not applied">\\u00d7</button>
    <a class="kt" href="${j.url}" target="_blank" rel="noopener" draggable="false"
       data-tip="Open the posting to apply">${j.title}</a><div class="kco">${j.comp}</div>
    <div class="kmeta"><span>${j.region}</span><span>\\u00b7</span><span>${j.age}</span>
      ${note ? '<span class="nbadge" data-tip="Has a note">\\u270e</span>' : ''}
      <span class="ks">${j.salary || ''}</span></div>`;
  return div;
}

function renderBoard() {
  BOARD_STAGES.forEach(k => {
    const box = document.getElementById('cb-' + k);
    const ids = Object.keys(APPS).filter(id => JOBS[id] && stage(id) === k);
    box.innerHTML = '';
    if (!ids.length) {
      box.innerHTML = '<div class="slot">Drag a role here</div>';
    } else {
      ids.forEach((id, i) => {
        const c = kcard(id);
        c.style.animationDelay = (i * 22) + 'ms';
        box.appendChild(c);
      });
    }
    bump(document.getElementById('cn-' + k), ids.length);
    // Applied always stays open — it is the drop target you reach for first.
    document.getElementById('dz-' + k).classList.toggle(
      'rail', ids.length === 0 && k !== BOARD_STAGES[0]);
  });
  const railed = BOARD_STAGES.filter(
    k => document.getElementById('dz-' + k).classList.contains('rail')).length;
  const lp = document.getElementById('listpane');
  [1, 2, 3].forEach(n => lp.classList.toggle('w' + n, railed === n));
  CLOSED_STAGES.forEach(k => {
    bump(document.getElementById('cn-' + k),
         Object.keys(APPS).filter(id => JOBS[id] && stage(id) === k).length);
  });
}

/* ------------------------------------------------------------ drag & drop */

let dragId = null;

function onDragStart(el, id) {
  dragId = id;
  el.classList.add('dragging');
  document.body.classList.add('dragging-active');
}
function onDragEnd(el) {
  el.classList.remove('dragging');
  dragId = null;
  $$('.over').forEach(e => e.classList.remove('over'));
  $('#listpane').classList.remove('dropping');
}

rowsEl.addEventListener('dragstart', e => {
  const r = e.target.closest('.row'); if (!r) return;
  e.dataTransfer.effectAllowed = 'move';
  onDragStart(r, r.dataset.id);
});
rowsEl.addEventListener('dragend', e => {
  const r = e.target.closest('.row'); if (r) onDragEnd(r);
});

function wireDropZone(el, stageKey) {
  el.addEventListener('dragover', e => {
    if (!dragId) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'move';
    el.classList.add('over');
  });
  el.addEventListener('dragleave', e => {
    if (!el.contains(e.relatedTarget)) el.classList.remove('over');
  });
  el.addEventListener('drop', e => {
    e.preventDefault(); el.classList.remove('over');
    if (dragId) move(dragId, stageKey);
  });
}
BOARD_STAGES.concat(CLOSED_STAGES).forEach(k =>
  wireDropZone(document.getElementById('dz-' + k), k));

// Dropping back onto the list un-tracks the role.
const lp = $('#listpane');
lp.addEventListener('dragover', e => {
  if (!dragId || stage(dragId) === 'none') return;
  e.preventDefault(); lp.classList.add('dropping');
});
lp.addEventListener('dragleave', e => {
  if (!lp.contains(e.relatedTarget)) lp.classList.remove('dropping');
});
lp.addEventListener('drop', e => {
  lp.classList.remove('dropping');
  if (dragId && stage(dragId) !== 'none') { e.preventDefault(); move(dragId, 'none'); }
});

$('.cols').addEventListener('dragstart', e => {
  const c = e.target.closest('.kc'); if (!c) return;
  e.dataTransfer.effectAllowed = 'move';
  onDragStart(c, c.dataset.id);
});
$('.cols').addEventListener('dragend', e => {
  const c = e.target.closest('.kc'); if (c) onDragEnd(c);
});
$('.cols').addEventListener('click', e => {
  const x = e.target.closest('.kx');
  if (x) { move(x.closest('.kc').dataset.id, 'none'); return; }
  if (e.target.closest('a')) return;        // opening the posting is not a note
  const card = e.target.closest('.kc');
  if (!card || e.target.classList.contains('knote')) return;
  let n = card.querySelector('.knote');
  if (n) { n.remove(); return; }
  n = document.createElement('textarea');
  n.className = 'knote';
  n.placeholder = 'Notes \\u2014 recruiter, referral, follow-up\\u2026';
  n.value = (APPS[card.dataset.id] || {}).note || '';
  n.addEventListener('click', ev => ev.stopPropagation());
  n.addEventListener('input', () => {
    const e2 = APPS[card.dataset.id]; if (!e2) return;
    e2.note = n.value; saveApps();
  });
  card.appendChild(n); n.focus();
});

/* ----------------------------------------------------------- row actions */

rowsEl.addEventListener('click', e => {
  const btn = e.target.closest('.iact'); if (!btn) return;
  const id = btn.closest('.row').dataset.id;
  if (btn.dataset.act === 'open') window.open(JOBS[id].url, '_blank', 'noopener');
  if (btn.dataset.act === 'apply') move(id, 'applied');
});

/* ----------------------------------------------------------------- flow */

function buildFlows() {
  const track = BOARD_STAGES.concat(['accepted']);
  const reached = {}, flows = new Map();
  track.forEach(k => reached[k] = 0);
  let applied = 0;
  Object.keys(APPS).forEach(id => {
    if (!JOBS[id]) return;
    const e = APPS[id];
    const hist = (e.history && e.history.length ? e.history.map(h => h.stage) : [e.status])
      .filter(s => s && s !== 'none');
    if (!hist.length) return;
    const path = hist.filter((s, i) => i === 0 || s !== hist[i - 1]);
    if (!path.includes('applied')) path.unshift('applied');
    applied++;
    new Set(path.filter(s => track.includes(s))).forEach(s => reached[s]++);
    for (let i = 0; i < path.length - 1; i++) {
      const key = path[i] + '>' + path[i + 1];
      flows.set(key, (flows.get(key) || 0) + 1);
    }
  });
  return { reached, flows, applied, track };
}

function drawSankey() {
  const svg = $('#sankey'), empty = $('#flowEmpty');
  const { reached, flows, applied, track } = buildFlows();
  $('#funnel').innerHTML = track.map((k, i) => {
    const v = reached[k] || 0;
    const base = i === 0 ? applied : (reached[track[i - 1]] || 0);
    const rate = i === 0 || !base ? '' : Math.round(v / base * 100) + '% of ' + label(track[i - 1]);
    return `<div class="fstat" style="--bar:var(${cvar(k)});--d:${i * 55}ms"><div class="fv">${v}</div>`
      + `<div class="fl">${label(k)}</div><div class="fr">${rate || '&nbsp;'}</div></div>`;
  }).join('');

  if (!applied) { svg.innerHTML = ''; svg.classList.add('hidden');
                   empty.classList.remove('hidden'); return; }
  svg.classList.remove('hidden'); empty.classList.add('hidden');

  const colOf = {}; track.forEach((k, i) => colOf[k] = i);
  const nodes = {};
  track.forEach(k => { if (reached[k]) nodes[k] = { v: reached[k], stage: k, col: colOf[k] }; });
  flows.forEach((v, key) => {
    const [a, b] = key.split('>');
    if (!CLOSED_STAGES.includes(b) || colOf[a] === undefined || b === 'accepted') return;
    nodes[b + '@' + a] = { v, stage: b, col: colOf[a] + 1 };
  });

  const byCol = {};
  Object.entries(nodes).forEach(([id, n]) => (byCol[n.col] = byCol[n.col] || []).push(id));
  const colIdx = Object.keys(byCol).map(Number).sort((a, b) => a - b);
  const maxSum = Math.max(...colIdx.map(c => byCol[c].reduce((a, id) => a + nodes[id].v, 0)));

  const W = svg.clientWidth || 1000, H = Math.max(240, svg.clientHeight || 300);
  const colW = 15, gap = 6, labelW = 132;
  const padT = 16, padB = 16, plot = H - padT - padB;
  const unit = plot / Math.max(maxSum, 1);
  const span = Math.max(1, colIdx[colIdx.length - 1]);
  const xOf = c => 8 + (c / span) * (W - colW - labelW - 16);

  const pos = {};
  colIdx.forEach(c => {
    const ids = byCol[c].sort((a, b) => (CLOSED_STAGES.includes(nodes[a].stage) ? 1 : 0)
                                      - (CLOSED_STAGES.includes(nodes[b].stage) ? 1 : 0));
    let y = padT;
    ids.forEach(id => {
      const h = Math.max(5, nodes[id].v * unit);
      pos[id] = { x: xOf(c), y, h, inY: y, outY: y };
      y += h + gap;
    });
  });

  const ribbons = [];
  flows.forEach((v, key) => {
    const [a, b] = key.split('>');
    const t = (CLOSED_STAGES.includes(b) && b !== 'accepted') ? b + '@' + a : b;
    if (pos[a] && pos[t]) ribbons.push({ a, t, b, v });
  });
  ribbons.sort((x, y) => nodes[x.t].col - nodes[y.t].col || y.v - x.v);

  let out = '';
  ribbons.forEach(f => {
    const s = pos[f.a], t = pos[f.t], th = Math.max(2, f.v * unit);
    const y0 = s.outY, y1 = t.inY;
    s.outY += th; t.inY += th;
    const x0 = s.x + colW, x1 = t.x, mx = (x0 + x1) / 2;
    out += `<path class="sk-flow" opacity=".4" fill="var(${cvar(f.a)})"`
      + ` d="M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1} L${x1},${y1 + th}`
      + ` C${mx},${y1 + th} ${mx},${y0 + th} ${x0},${y0 + th} Z"`
      + ` data-tip="${label(f.a)} &rarr; ${label(f.b)}: ${f.v}"></path>`;
  });
  Object.entries(pos).forEach(([id, p]) => {
    const n = nodes[id];
    out += `<rect class="sk-node" x="${p.x}" y="${p.y}" width="${colW}" height="${p.h}" rx="3"`
      + ` fill="var(${cvar(n.stage)})" data-tip="${label(n.stage)}: ${n.v}"></rect>`
      + `<text class="sk-val" x="${p.x + colW + 9}" y="${p.y + p.h / 2 - 1}">${n.v}</text>`
      + `<text class="sk-lab" x="${p.x + colW + 9}" y="${p.y + p.h / 2 + 13}">${label(n.stage)}</text>`;
  });
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = out;
}

// One tooltip for the whole page. Native title= was used at first and simply
// did not read as an explanation — it needs a hover-and-wait, gives no hint
// that there is anything to read, and styles itself like an OS error.
const fbox = $('#flowbox');
function placeTip(e) {
  const pad = 12;
  let x = e.clientX + 14, y = e.clientY + 18;
  if (x + tip.offsetWidth > innerWidth - pad) x = e.clientX - tip.offsetWidth - 14;
  if (y + tip.offsetHeight > innerHeight - pad) y = e.clientY - tip.offsetHeight - 14;
  tip.style.left = Math.max(pad, x) + 'px';
  tip.style.top = Math.max(pad, y) + 'px';
}
// Tooltips wait for a deliberate hover. Firing instantly meant that sweeping
// the mouse down a 177-row list set off a popup on every row. Once one IS open,
// moving to a neighbour shows immediately for a moment — reading two rows in a
// row should not cost two waits.
const TIP_DELAY = 800, TIP_CHAIN = 500;
let tipTimer = null, chainUntil = 0, at = { clientX: 0, clientY: 0 };

function showTip(el) {
  tip.innerHTML = el.dataset.tip;
  tip.classList.remove('hidden');
  placeTip(at);
  if (el.closest('#sankey')) { fbox.classList.add('dim'); el.classList.add('hot'); }
}
document.addEventListener('mouseover', e => {
  const el = e.target.closest('[data-tip]'); if (!el) return;
  at = { clientX: e.clientX, clientY: e.clientY };
  clearTimeout(tipTimer);
  if (Date.now() < chainUntil) showTip(el);
  else tipTimer = setTimeout(() => showTip(el), TIP_DELAY);
});
document.addEventListener('mousemove', e => {
  at = { clientX: e.clientX, clientY: e.clientY };
  if (!tip.classList.contains('hidden')) placeTip(e);
});
document.addEventListener('mouseout', e => {
  const el = e.target.closest('[data-tip]'); if (!el) return;
  clearTimeout(tipTimer);
  if (!tip.classList.contains('hidden')) chainUntil = Date.now() + TIP_CHAIN;
  el.classList.remove('hot');
  fbox.classList.remove('dim');
  tip.classList.add('hidden');
});

/* ------------------------------------------------------------------- csv */

// A real .xlsx would mean writing a zip container and OOXML by hand, which is
// not worth the weight in a page that must stay self-contained. A UTF-8 CSV
// with a BOM and CRLF line ends is what Excel actually wants: double-clicking
// it opens with encoding and columns intact.
// NB: this block avoids backslash escapes on purpose. The JS in this file
// lives inside a plain (non-raw) Python string, so Python consumes tab,
// carriage-return and unicode escapes before the browser ever sees them, and a
// literal CR inside a JS string literal is a syntax error that takes the whole
// page down. Building the control characters by code point sidesteps it.
const TAB = String.fromCharCode(9), CR = String.fromCharCode(13);
const CRLF = String.fromCharCode(13, 10), BOM = String.fromCharCode(65279);
// Excel executes a cell that opens with any of these. Titles come from job
// boards and notes are typed, so neither is trustworthy input.
const CSV_RISKY = ['=', '+', '-', '@', TAB, CR];

function csvCell(v) {
  let s = v === null || v === undefined ? '' : String(v);
  if (CSV_RISKY.indexOf(s.charAt(0)) !== -1) s = "'" + s;
  return '"' + s.split('"').join('""') + '"';
}

function downloadCSV(name, header, rows) {
  if (!rows.length) { toast('Nothing to export yet', null); return; }
  const body = [header].concat(rows).map(r => r.map(csvCell).join(',')).join(CRLF);
  const blob = new Blob([BOM + body], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name + '-' + new Date().toISOString().slice(0, 10) + '.csv';
  a.click();
  URL.revokeObjectURL(a.href);
  toast('Exported ' + rows.length + ' row' + (rows.length === 1 ? '' : 's'), null);
}

function exportPipeline() {
  const rows = Object.keys(APPS).filter(id => JOBS[id] && stage(id) !== 'none').map(id => {
    const j = JOBS[id], e = APPS[id], h = e.history || [];
    return [j.comp, j.title, label(stage(id)), e.applied_date || '',
            h.length ? h[0].date : '', h.length ? h[h.length - 1].date : '',
            h.map(x => label(x.stage)).join(' > '),
            j.score, j.salary, j.region, j.age,
            (e.note || '').split(String.fromCharCode(10)).join(' '), j.url];
  });
  downloadCSV('jobscope-pipeline',
    ['Company', 'Role', 'Stage', 'Applied', 'First moved', 'Last moved', 'Path',
     'Score', 'Salary', 'Location', 'Posted', 'Note', 'URL'], rows);
}

function exportVisible() {
  const rows = rows_.filter(r => !r.classList.contains('hidden')).map(r => {
    const j = JOBS[r.dataset.id] || {};
    return [j.comp, j.title, r.dataset.score, label(stage(r.dataset.id)),
            j.region, j.age, j.salary, r.dataset.level === 'none' ? '' : r.dataset.level,
            r.dataset.yoe === 'na' ? '' : r.dataset.yoe,
            r.dataset.spon || '', r.dataset.ghost === '1' ? 'yes' : '', j.url];
  });
  downloadCSV('jobscope-roles',
    ['Company', 'Role', 'Score', 'Stage', 'Location', 'Posted', 'Salary', 'Level',
     'Experience', 'Sponsorship', 'Possible ghost', 'URL'], rows);
}

$('#csvPipe').addEventListener('click', exportPipeline);
$('#csvAll').addEventListener('click', exportVisible);

/* ------------------------------------------------------- companies sheet */

const compOv = $('#compOv'), compQ = $('#compQ'), compBody = $('#compBody');

function compCard(c) {
  const dim = c.m ? '' : ' dim';
  const bits = [c.src];
  if (c.p) bits.push(c.p + ' open');
  const meta = c.e ? `<div class="cmeta err">${c.src} &middot; ${c.e}</div>`
                   : `<div class="cmeta">${bits.join(' &middot; ')}</div>`;
  const go = c.u ? `<a class="cgo" href="${c.u}" target="_blank" rel="noopener"
                       data-tip="Open the careers page">&#8599;</a>` : '';
  return `<div class="ccard${dim}" data-slug="${c.g}" data-name="${c.n}">
    <div class="cinfo"><div class="cname">${c.n}</div>${meta}</div>
    <span class="ccount">${c.m}</span>${go}</div>`;
}

function renderCompanies() {
  const term = compQ.value.trim().toLowerCase();
  const list = COMPANIES.filter(c => !term || c.n.toLowerCase().includes(term));
  const hit = list.filter(c => c.m > 0);
  const miss = list.filter(c => !c.m && !c.e);
  const bad = list.filter(c => !c.m && c.e);
  let out = '';
  const grp = (lab, arr) => {
    if (!arr.length) return;
    out += `<div class="cgrp">${lab} &middot; ${arr.length}</div>`
         + `<div class="cgrid">${arr.map(compCard).join('')}</div>`;
  };
  grp('With matching roles &mdash; click to filter the list', hit);
  grp('Searched, nothing matched', miss);
  grp('Could not be fetched', bad);
  compBody.innerHTML = out || '<div class="fddempty">No company matches that name.</div>';
  $('#compSub').textContent = COMPANIES.length + ' searched \\u00b7 '
    + COMPANIES.filter(c => c.m).length + ' with roles';
}

function openCompanies() {
  compQ.value = '';
  renderCompanies();
  compOv.classList.remove('hidden');
  compQ.focus();
}
const closeCompanies = () => compOv.classList.add('hidden');

$('#kCompanies').addEventListener('click', openCompanies);
$('#kCompanies').addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCompanies(); }
});
$('#compX').addEventListener('click', closeCompanies);
compOv.addEventListener('click', e => { if (e.target === compOv) closeCompanies(); });
compQ.addEventListener('input', renderCompanies);
compBody.addEventListener('click', e => {
  if (e.target.closest('.cgo')) return;              // the careers link is its own thing
  const card = e.target.closest('.ccard');
  if (!card || card.classList.contains('dim')) return;
  facets.company.clear();
  facets.company.add(card.dataset.slug);
  q.value = '';
  closeCompanies();
  showTab('board');
  render();
  // Its roles can still all be stale or already tracked, and a list that goes
  // empty right after a click reads as a broken filter rather than an active one.
  if ($('#shown').textContent === '0')
    toast(card.dataset.name + ': every role is hidden by your other filters', null);
});

/* ----------------------------------------------------------------- views */

function showTab(name) {
  $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.view === name));
  $('#viewBoard').classList.toggle('hidden', name !== 'board');
  $('#viewFlow').classList.toggle('hidden', name !== 'flow');
  $('#listpane').classList.toggle('hidden', name === 'flow');
  if (name === 'flow') requestAnimationFrame(drawSankey);
  saveView();
}
$$('.tab').forEach(t => t.addEventListener('click', () => showTab(t.dataset.view)));

/* ---------------------------------------------------------------- render */

let staggered = false;
function render() {
  let n = 0;
  rows.forEach(r => {
    const show = passes(r, null);
    r.classList.toggle('hidden', !show);
    if (show) {
      if (!staggered && n < 26) r.style.setProperty('--d', (n * 16) + 'ms');
      n++;
    }
    const st = stage(r.dataset.id);
    r.classList.toggle('tracked', st !== 'none');
    const dot = r.querySelector('.stagedot');
    if (st === 'none') { if (dot) dot.remove(); }
    else {
      const d = dot || Object.assign(document.createElement('span'), { className: 'stagedot' });
      d.style.color = `var(${cvar(st)})`;
      d.style.background = 'currentColor';
      d.title = label(st);
      if (!dot) r.querySelector('.rt').appendChild(d);
    }
  });
  staggered = true;
  $('#shown').textContent = n;
  $('#emptyList').classList.toggle('hidden', n !== 0);
  const tracked = Object.keys(APPS).filter(id => JOBS[id] && stage(id) !== 'none');
  $('#kTracked').textContent = tracked.length;
  $$('.fdd').forEach(dd => {
    const fields = dd.dataset.facet ? [dd.dataset.facet] : JSON.parse(dd.dataset.fields || '[]');
    const c = fields.reduce((a, f) => a + facets[f].size, 0);
    const b = dd.querySelector('.fbtn');
    b.classList.toggle('on', c > 0);
    const badge = b.querySelector('.n');
    if (badge) { badge.textContent = c; badge.classList.toggle('hidden', !c); }
  });
  renderBoard();
  if (!$('#viewFlow').classList.contains('hidden')) drawSankey();
  saveView();
}

/* ------------------------------------------------------------ view state */

function saveView() {
  const p = new URLSearchParams();
  if (q.value) p.set('q', q.value);
  if (sortKey !== 'score' || sortDir !== -1) p.set('sort', sortKey + (sortDir === 1 ? '.a' : ''));
  if (!freshOnly) p.set('fresh', '0');
  if (newOnly) p.set('new', '1');
  if (hideGhosts) p.set('noghost', '1');
  if (!$('#viewFlow').classList.contains('hidden')) p.set('view', 'flow');
  for (const f in facets) if (facets[f].size) p.set(f, [...facets[f]].join('~'));
  const s = p.toString();
  history.replaceState(null, '', s ? '#' + s : location.pathname);
  localStorage.setItem(VIEWKEY, s);
}

function loadView() {
  const raw = location.hash.length > 1 ? location.hash.slice(1)
                                       : (localStorage.getItem(VIEWKEY) || '');
  if (!raw) return null;
  const p = new URLSearchParams(raw);
  q.value = p.get('q') || '';
  if (p.get('sort')) {
    const [k, a] = p.get('sort').split('.');
    sortKey = k; sortDir = a === 'a' ? 1 : -1;
  }
  freshOnly = p.get('fresh') !== '0';
  newOnly = p.get('new') === '1';
  hideGhosts = p.get('noghost') === '1';
  for (const f in facets) if (p.get(f)) p.get(f).split('~').forEach(v => facets[f].add(v));
  return p.get('view');
}

/* ---------------------------------------------------------------- wiring */

q.addEventListener('input', render);
$('#freshBtn').addEventListener('click', e => {
  freshOnly = !freshOnly; e.target.classList.toggle('on', freshOnly); render();
});
$('#newBtn').addEventListener('click', e => {
  newOnly = !newOnly; e.target.classList.toggle('on', newOnly); render();
});
$('#ghostBtn').addEventListener('click', e => {
  hideGhosts = !hideGhosts; e.target.classList.toggle('on', hideGhosts); render();
});
$('#clrBtn').addEventListener('click', () => {
  for (const f in facets) facets[f].clear();
  newOnly = hideGhosts = false; freshOnly = false;
  ['freshBtn', 'newBtn', 'ghostBtn'].forEach(i => $('#' + i).classList.remove('on'));
  q.value = ''; render();
});
// The wordmark is the way back to the start: default view, nothing filtered.
// ctrl/middle-click still follows the href and reloads the page instead.
$('.brand').addEventListener('click', e => {
  if (e.ctrlKey || e.metaKey || e.shiftKey) return;
  e.preventDefault();
  closeCompanies();
  closeMenus();
  for (const f in facets) facets[f].clear();
  newOnly = hideGhosts = false; freshOnly = true;
  q.value = '';
  sortKey = 'score'; sortDir = -1;
  $('#freshBtn').classList.add('on');
  ['newBtn', 'ghostBtn'].forEach(i => $('#' + i).classList.remove('on'));
  $$('.lhead span').forEach(x => x.classList.toggle('sorted', x.dataset.sort === sortKey));
  sortRows();
  showTab('board');
  render();
  rowsEl.scrollTop = 0;
});
$('.lhead').addEventListener('click', e => {
  const s = e.target.closest('[data-sort]'); if (!s) return;
  const k = s.dataset.sort;
  if (sortKey === k) sortDir = -sortDir;
  else { sortKey = k; sortDir = (k === 'title' || k === 'company' || k === 'location') ? 1 : -1; }
  $$('.lhead span').forEach(x => x.classList.toggle('sorted', x.dataset.sort === sortKey));
  sortRows(); saveView();
});
addEventListener('resize', () => {
  if (!$('#viewFlow').classList.contains('hidden')) drawSankey();
});
addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeMenus(); closeCompanies(); tip.classList.add('hidden'); }
  if (e.key === '/' && e.target !== q && e.target !== compQ) { e.preventDefault(); q.focus(); }
});

repairHistory();
const view = loadView();
$('#freshBtn').classList.toggle('on', freshOnly);
$('#newBtn').classList.toggle('on', newOnly);
$('#ghostBtn').classList.toggle('on', hideGhosts);
$$('.lhead span').forEach(x => x.classList.toggle('sorted', x.dataset.sort === sortKey));
sortRows();
showTab(view === 'flow' ? 'flow' : 'board');
render();
"""
