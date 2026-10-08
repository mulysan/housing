# PNG copy of the binned scatters (junctions, businesses, commerce share), raw vs within city, for chat/wiki.
import json, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, sys
U = json.load(open('urban_v3.json'))
panels = [('Junctions per km² (log)', U['bins_raw'], U['bins_city'], np.exp, [10, 25, 50, 100, 200], np.log),
          ('Businesses per km² (log; SAs with none excluded)', U['bins_comm']['l_comm']['raw'], U['bins_comm']['l_comm']['city'], np.expm1, [3, 10, 30, 100, 300, 1000, 3000], np.log),
          ('Commerce share of land use', U['bins_comm']['comm_share']['raw'], U['bins_comm']['comm_share']['city'], None, [0, .05, .1, .2, .3, .4, .6, .8], lambda v: v)]
fig, ax = plt.subplots(1, 3, figsize=(15, 4.4), sharey=True)
for a, (t, raw, city, inv, ticks, tx) in zip(ax, panels):
    for rows, c, l in [(raw, '#9a9a9a', 'all Israel'), (city, '#d9480f', 'vs own city mean')]:
        r = np.array(rows); a.scatter(r[:, 0], 100*(np.exp(r[:, 1]) - 1), s=28, c=c, label=l)
    a.axhline(0, c='k', lw=.6); a.set_xticks([tx(v) for v in ticks]); a.set_xticklabels([f'{v:g}' if inv is not None else f'{v:.0%}' for v in ticks])
    a.set_title(t); a.grid(alpha=.3)
ax[0].set_ylabel('Building price effect (% vs mean)'); ax[0].legend(loc='upper left')
fig.suptitle('Building fixed effect (real ln price/m²) by 20 equal-size bins of the SA measure (x in its own units)', fontsize=11)
fig.tight_layout(); fig.savefig(sys.argv[1], dpi=130); print('saved')
