# Deploy the dashboard to Vercel

This publishes the self-contained dashboard (`public/index.html`) as a real
website — a stable URL, no sandbox, so Export and everything else work. It's the
static snapshot (fixed example numbers), which is what a no-setup viewer wants.

## One-time: import the repo (about 3 clicks)

1. Go to **vercel.com/new**.
2. **Import** the `rpedreschi/attribution-agent` repository.
   (If Vercel can't see it, click *Adjust GitHub App Permissions* and grant it.)
3. Leave every setting at its default — `vercel.json` already tells Vercel to
   serve the `public/` folder with no build step — and click **Deploy**.

That's it. Vercel gives you a URL like `attribution-agent.vercel.app`. Share
that link; nothing to install for whoever opens it.

## Updating the site

Every push to `main` redeploys automatically. To refresh the numbers or the UI:

```
python scripts/build_static_ui.py
git add public/index.html ui/deltastream-pulse.html
git commit -m "Refresh dashboard"
git push
```

`build_static_ui.py` writes `public/index.html` (what Vercel serves) on every
run. To bake in **live** numbers instead of the example board, run it with
`--source mcp` first (needs the DeltaStream login in `.env`).

## Custom domain (optional)

In the Vercel project: **Settings → Domains → Add**, then point a subdomain
(e.g. `pulse.deltastream.io`) at it. Vercel walks you through the DNS record.

## Notes

- This is the static dashboard — the numbers don't stream. For a live,
  moving demo, that's the datagen path in `ui/GUIDE.md`, not Vercel.
- Only `public/` is served. The rest of the repo (source, scripts) isn't
  exposed by the site.
