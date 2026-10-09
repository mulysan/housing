# Figures for the dwelling-size paper (wiki/papers/own/dwelling-size/fig/), from size_paper.json.
import json, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
O = json.load(open('size_paper.json')); OUTD = '/home/user/-econ-research-wiki/wiki/papers/own/dwelling-size/fig/'
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']; INK, MUTED, GRID = '#0b0b0b', '#52514e', '#e4e3df'
SZ = ['1-2', '3', '4', '5+']; SZL = {'1-2': '1–2 rooms', '3': '3 rooms', '4': '4 rooms', '5+': '5+ rooms'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID,
                     'grid.linewidth': 0.8, 'axes.axisbelow': True, 'figure.dpi': 150, 'savefig.bbox': 'tight', 'legend.frameon': False})
def label_end(ax, x, y, text, color, dy=0):
    ax.annotate(text, (x[-1], y[-1]), xytext=(6, dy), textcoords='offset points', va='center', color=INK, fontsize=9)
# Fig 1: composition of completions by building year
b = O['built_share']; y = np.array(b['y'])
fig, ax = plt.subplots(figsize=(7, 4))
offs = {'1-2': -4, '3': 4, '4': -2, '5+': 6}
for k, s in enumerate(SZ):
    v = np.array(b[s]) * 100; v5 = np.convolve(v, np.ones(3)/3, mode='same'); v5[0], v5[-1] = v[0], v[-1]
    ax.plot(y, v5, color=C[k], lw=2, label=SZL[s]); label_end(ax, y, v5, SZL[s], C[k], offs[s])
ax.set_xlim(1950, 2026); ax.set_ylim(0, 60); ax.set_ylabel('share of completions (%)'); ax.set_xlabel('building year (3-year moving average)')
ax.legend(loc='upper center', ncol=4, fontsize=8.5, bbox_to_anchor=(0.5, 1.08))
fig.savefig(OUTD + 'fig1_completions_by_size.png'); plt.close(fig)
# Fig 2: mean m2 and rooms of dwellings sold, by building decade (two panels, one axis each)
bd = O['by_building_decade']; dec = sorted(int(k) for k in bd)
fig, axs = plt.subplots(1, 2, figsize=(8, 3.3))
axs[0].bar([str(d) + 's' for d in dec], [bd[str(d)]['m2'] for d in dec], color=C[0], width=0.7)
axs[0].set_ylabel('mean recorded area (m²)'); axs[0].set_title('(a) area', loc='left', fontsize=10, color=INK)
axs[1].bar([str(d) + 's' for d in dec], [bd[str(d)]['rooms'] for d in dec], color=C[0], width=0.7)
axs[1].set_ylabel('mean rooms'); axs[1].set_title('(b) rooms', loc='left', fontsize=10, color=INK); axs[1].set_ylim(2, 4.8)
for ax in axs: ax.tick_params(axis='x', rotation=45); ax.grid(axis='x', visible=False)
fig.text(0.5, -0.06, 'building decade; all sales 1998–2025 (Tax Authority + govmap)', ha='center', color=MUTED, fontsize=9)
fig.savefig(OUTD + 'fig2_size_by_decade.png'); plt.close(fig)
# Fig 3: within building x year price-per-m2 gradient by rooms, by period
g = O['gradient_within_building_year']; P = ['1998-2005', '2006-2012', '2013-2019', '2020-2025']
fig, ax = plt.subplots(figsize=(7, 4))
for k, p in enumerate(P):
    r = g[p]['rooms']; xs = sorted(int(x) for x in r); ys = [r[str(x)] * 100 for x in xs]
    ax.plot(xs, ys, color=C[k], lw=2, marker='o', ms=5, label=p.replace('-', '–'))
ax.axhline(0, color=MUTED, lw=1); ax.set_xticks(range(1, 8)); ax.set_xlabel('rooms (rounded up)'); ax.set_ylabel('price per m² vs 4 rooms, same building and year (%)')
ax.legend(title='sale period', fontsize=8.5, title_fontsize=8.5)
fig.savefig(OUTD + 'fig3_gradient_by_period.png'); plt.close(fig)
# Fig 4: national relative supply and relative price by size class (two panels)
ns = O['national_series']
fig, axs = plt.subplots(1, 2, figsize=(9, 3.6))
th = {s: dict(zip(ns[s]['t'], ns[s]['theta'])) for s in SZ}; ls = {s: dict(zip(ns[s]['t'], ns[s]['lS'])) for s in SZ}
T = sorted(set.intersection(*[set(th[s]) for s in SZ]))
for k, s in enumerate(SZ):
    rel_s = np.array([ls[s][t] - np.mean([ls[o][t] for o in SZ]) for t in T]); rel_s -= rel_s[0]
    rel_p = np.array([th[s][t] - np.mean([th[o][t] for o in SZ]) for t in T]); rel_p -= rel_p[0]
    axs[0].plot(T, rel_s * 100, color=C[k], lw=2); label_end(axs[0], T, rel_s * 100, SZL[s], C[k])
    axs[1].plot(T, rel_p * 100, color=C[k], lw=2); label_end(axs[1], T, rel_p * 100, SZL[s], C[k], {'3': 5, '4': -5}.get(s, 0))
axs[0].set_title('(a) relative stock (log points ×100, 1998 = 0)', loc='left', fontsize=10, color=INK)
axs[1].set_title('(b) relative price per m² (log points ×100, 1998 = 0)', loc='left', fontsize=10, color=INK)
for ax in axs: ax.set_xlim(1998, 2024); ax.axhline(0, color=MUTED, lw=1)
fig.savefig(OUTD + 'fig4_relative_supply_price.png'); plt.close(fig)
# Fig 5: cross-size matrix (relative to column mean), diverging blue-gray-orange
M = np.array(O['km']['matrix_dt']['b_rel'])
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list('div', ['#2a78d6', '#ecebe7', '#eb6834'])
fig, ax = plt.subplots(figsize=(5, 4.2)); vmax = np.abs(M).max()
im = ax.imshow(M, cmap=cmap, vmin=-vmax, vmax=vmax)
for i in range(4):
    for j in range(4): ax.text(j, i, f'{M[i, j]:+.2f}', ha='center', va='center', color=INK, fontsize=9)
ax.set_xticks(range(4)); ax.set_xticklabels([SZL[s] for s in SZ], rotation=30); ax.set_yticks(range(4)); ax.set_yticklabels([SZL[s] for s in SZ])
ax.set_xlabel('log stock of size k in the district (t−1)'); ax.set_ylabel('price of size s'); ax.grid(False)
fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label('elasticity, relative to column mean')
fig.savefig(OUTD + 'fig5_cross_size_matrix.png'); plt.close(fig)
# Fig 6: break-even per-unit cost c* by district (1-2 and 3 rooms vs 4)
cs = O['c_star']; D = list(cs)
fig, ax = plt.subplots(figsize=(7.5, 3.6)); x = np.arange(len(D)); w = 0.36
ax.bar(x - w/2 - 0.01, [cs[d]['1-2']*1000 for d in D], w, color=C[0], label='1–2 rooms vs 4')
ax.bar(x + w/2 + 0.01, [cs[d]['3']*1000 for d in D], w, color=C[1], label='3 rooms vs 4')
ax.set_xticks(x); ax.set_xticklabels(D, rotation=20); ax.set_ylabel('break-even extra cost per dwelling (NIS 000)'); ax.legend(fontsize=8.5); ax.grid(axis='x', visible=False)
fig.savefig(OUTD + 'fig6_break_even_cost.png'); plt.close(fig)
# Fig 7: welfare and dwellings added under the optimal mix vs true per-unit cost c (s0 = 0.2)
fig, axs = plt.subplots(1, 2, figsize=(9, 3.4)); cs_ = [0.0, 0.02, 0.05, 0.10, 0.15, 0.30]
for k, (bl, lab) in enumerate([('district_x_year', 'σ_size from district × year (−0.10)'), ('national', 'σ_size national (−0.19)')]):
    rr = [O['cf'][f'{bl}|s0=0.2|c={c}']['total']['optimal'] for c in cs_]
    axs[0].plot(np.array(cs_)*1000, [r['dW']/1000 for r in rr], color=C[k], lw=2, marker='o', ms=5, label=lab)
    axs[1].plot(np.array(cs_)*1000, [r['dN']/1000 for r in rr], color=C[k], lw=2, marker='o', ms=5, label=lab)
axs[0].set_ylabel('net welfare gain (NIS bn)'); axs[1].set_ylabel('dwellings added (000)')
for ax in axs: ax.set_xlabel('true resource cost of an extra dwelling (NIS 000)'); ax.axhline(0, color=MUTED, lw=1)
axs[0].legend(fontsize=8)
fig.savefig(OUTD + 'fig7_counterfactual.png'); plt.close(fig)
# Fig 8: the supply-price relation by dwelling size (Katz-Murphy). (a) partial-residual plot of the district x size
# panel after district x year and market FE (the variation that identifies b); (b) long differences 1998-2019,
# within district;
# (c) national connected scatter of relative price against relative stock, 5+ vs 1-2 rooms, 1998-2020.
K = O['km']; fr = K['fig_resid']; fl = K['fig_longdiff']; b_ = fr['slope']
fig, axs = plt.subplots(1, 3, figsize=(13, 3.9))
px, py, psz = np.array(fr['pts']['x']), np.array(fr['pts']['y']), np.array(fr['pts']['sz'])
for k, s in enumerate(SZ):
    m = psz == s; axs[0].scatter(px[m]*100, py[m]*100, s=7, color=C[k], alpha=0.35, lw=0, label=SZL[s])
axs[0].scatter(np.array(fr['bins']['x'])*100, np.array(fr['bins']['y'])*100, s=28, color=INK, zorder=3, label='ventile means')
xx = np.array([px.min(), px.max()]); axs[0].plot(xx*100, b_*xx*100, color=INK, lw=1.5)
axs[0].text(0.03, 0.04, f'slope b = {b_:.3f} ({fr["se"]:.3f})\nσ = 1/|b| ≈ {1/abs(b_):.0f}', transform=axs[0].transAxes, fontsize=9, color=INK, bbox=dict(facecolor='white', edgecolor=GRID, alpha=0.95))
axs[0].set_xlabel('log stock, residual (×100)'); axs[0].set_ylabel('log price per m², residual (×100)')
axs[0].set_title('(a) within market, net of district × year', loc='left', fontsize=10, color=INK); axs[0].legend(fontsize=7.5, loc='upper right', markerscale=1.5, frameon=True, facecolor='white', edgecolor=GRID, framealpha=0.95)
dS, dP, S_, fsz = np.array(fl['dS']), np.array(fl['dP']), np.array(fl['S']), np.array(fl['sz'])
for k, s in enumerate(SZ):
    m = fsz == s; axs[1].scatter(dS[m]*100, dP[m]*100, s=S_[m]/2500, color=C[k], alpha=0.8, lw=0.5, edgecolor='white')
xx = np.array([dS.min(), dS.max()]); a_ = np.average(dP - fl['slope']*dS, weights=S_)
axs[1].plot(xx*100, (a_ + fl['slope']*xx)*100, color=INK, lw=1.5)
axs[1].plot(xx*100, b_*xx*100, color=MUTED, lw=1.2, ls='--')
axs[1].text(0.03, 0.04, f'fitted slope {fl["slope"]:+.3f}\ndashed: b = {b_:.3f}', transform=axs[1].transAxes, fontsize=9, color=INK)
axs[1].set_xlabel('Δ log stock 1997–2018, minus district mean (×100)'); axs[1].set_ylabel('Δ log price 1998–2019, minus district mean (×100)')
axs[1].set_title('(b) long differences, 24 district × size markets', loc='left', fontsize=10, color=INK)
ns = O['national_series']; th = {s: dict(zip(ns[s]['t'], ns[s]['theta'])) for s in SZ}; ls_ = {s: dict(zip(ns[s]['t'], ns[s]['lS'])) for s in SZ}
T = sorted(set(th['1-2']) & set(th['5+'])); sig = 1/abs(b_)
rs = np.array([ls_['5+'][t] - ls_['1-2'][t] for t in T]); rp = np.array([th['5+'][t] - th['1-2'][t] for t in T]); rs -= rs[0]; rp -= rp[0]
axs[2].plot(rs*100, rp*100, color=C[0], lw=1.6, marker='o', ms=3.5)
for t, x_, y_ in zip(T, rs*100, rp*100):
    if t in (1998, 2002, 2005, 2008, 2011, 2014, 2017, 2020): axs[2].annotate(str(t), (x_, y_), xytext=(4, 4), textcoords='offset points', fontsize=8, color=MUTED)
x0 = rs[T.index(2005)]*100; y0 = rp[T.index(2005)]*100; xx = np.array([x0, rs[-1]*100])
axs[2].plot(xx, y0 + b_*(xx - x0), color=MUTED, lw=1.2, ls='--')
axs[2].axhline(0, color=MUTED, lw=1); axs[2].set_xlabel('relative stock, 5+ vs 1–2 rooms (log ×100, 1998 = 0)')
axs[2].set_ylabel('relative price per m² (log ×100, 1998 = 0)'); axs[2].set_title('(c) national path, 5+ vs 1–2 rooms', loc='left', fontsize=10, color=INK)
axs[2].text(0.97, 0.95, 'dashed: slope b from 2005', transform=axs[2].transAxes, ha='right', fontsize=8.5, color=MUTED)
fig.tight_layout(); fig.savefig(OUTD + 'fig8_supply_price_km.png'); plt.close(fig)
print('figures written')
