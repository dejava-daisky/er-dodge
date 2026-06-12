# ER Dodge Check - Netlify

This directory is a Netlify-specific copy of the original Flask project.

## Deploy

1. Push the `PROD` directory to a Git repository, or select `PROD` as the Netlify base directory.
2. Add `ER_API_KEY` in Netlify: **Site configuration > Environment variables**.
3. Deploy. No build command is required.

Netlify configuration:

- Publish directory: `public`
- Functions directory: `netlify/functions`
- API key: server-side environment variable `ER_API_KEY`

Patch data is bundled from `data/character_patches.json`. Update that file and redeploy when patch data changes.
