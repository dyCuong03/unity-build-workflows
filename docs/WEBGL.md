# WebGL Builds

This document covers WebGL build configuration and deployment for `unity-build-workflows`.

---

## Runner Requirements

WebGL builds run on **Ubuntu** or **macOS** runners. GitHub-hosted `ubuntu-latest` is recommended for cost efficiency.

Required:
- Unity Editor with WebGL Build Support module
- (Optional) Brotli compression tools for `compressionFormat: Brotli`

---

## BuildConfig Fields

Full reference in [BUILD_CONFIG.md](BUILD_CONFIG.md#webgl-object).

| Field | Default | Notes |
|---|---|---|
| `compressionFormat` | `Brotli` | Smallest files; requires server `Content-Encoding` header support |
| `decompressionFallback` | `true` | Always enable for static hosts (GitHub Pages, S3, etc.) |
| `dataCaching` | `true` | Reduces repeat load time via IndexedDB |
| `memorySize` | `256` | Increase for memory-heavy games; browser limit is typically 1–2GB |
| `template` | `Default` | `PWA` adds installability via service worker |
| `outputName` | — | Folder name inside `outputDirectory` |

---

## Compression Format Trade-offs

| Format | File Size | Server Requirement | Browser Support |
|---|---|---|---|
| `Brotli` | Smallest | Must serve `Content-Encoding: br` | All modern browsers |
| `Gzip` | Medium | Must serve `Content-Encoding: gzip` | Universal |
| `Disabled` | Largest | No special headers | Universal |

For hosting on servers you control (nginx, Apache), use `Brotli`. For static hosting services, check the service's header capabilities:

| Host | Recommended Format |
|---|---|
| GitHub Pages | `Gzip` with `decompressionFallback: true` |
| Netlify | `Brotli` (automatic header injection) |
| AWS S3 + CloudFront | `Brotli` (CloudFront supports br encoding) |
| itch.io | `Disabled` |

---

## Memory Configuration

The `memorySize` field sets the initial WASM heap in MB. Unity may grow the heap at runtime, but browsers have hard limits. Guidelines:

| Game Type | Recommended `memorySize` |
|---|---|
| Casual / Puzzle | 128–256 MB |
| Mid-core / RPG | 256–512 MB |
| Heavy 3D | 512–1024 MB |

If players see "Out of memory" errors in the browser console, increase `memorySize` by 128 MB increments. Mobile browsers typically cap WASM at 512–1024 MB.

---

## HTML Templates

### `Default`
Unity's standard loading screen with progress bar. Full Unity branding unless customized via `WebGLTemplates/` in the project.

### `Minimal`
Bare-bones HTML with no loading UI. Typically used as a base for custom templates.

### `PWA`
Adds a `manifest.json` and `service-worker.js` for Progressive Web App support. Allows "Add to Home Screen" on mobile.

### Custom Templates

Place custom templates under `Assets/WebGLTemplates/MyTemplate/` in the Unity project and reference them by folder name. Custom templates are not configured via BuildConfig — set `template: "Default"` and implement customization inside the Unity project's template directory.

---

## Build Output Structure

```
Builds/
  WebGL/
    index.html
    Build/
      MyGame.loader.js
      MyGame.data          # (or .data.br / .data.gz)
      MyGame.framework.js  # (or .framework.js.br / .framework.js.gz)
      MyGame.wasm          # (or .wasm.br / .wasm.gz)
    TemplateData/
      style.css
      favicon.ico
      ...
```

---

## Deployment

### GitHub Pages

```yaml
- name: Deploy to GitHub Pages
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./Builds/WebGL
```

Use `compressionFormat: Gzip` and `decompressionFallback: true` for GitHub Pages since it does not set `Content-Encoding` headers for pre-compressed files.

### Netlify

```yaml
- name: Deploy to Netlify
  uses: nwtgck/actions-netlify@v2
  with:
    publish-dir: './Builds/WebGL'
    production-branch: main
  env:
    NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
    NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
```

Add a `netlify.toml` to set headers:
```toml
[[headers]]
  for = "/*.br"
  [headers.values]
    Content-Encoding = "br"
    Content-Type = "application/octet-stream"
```

### AWS S3 + CloudFront

Use a post-build hook to sync to S3 with the correct `ContentEncoding` metadata, then trigger a CloudFront invalidation.

---

## Addressables with WebGL

WebGL supports Addressables with remote content hosting. Set `addressables.buildRemoteCatalog: true` and host bundles on a CDN. WebGL bundles use a different format than Android/iOS — ensure the Addressables remote loading path is set correctly in the `WebGL` Addressables profile.

---

## Troubleshooting

**"RangeError: Out of memory"**
Increase `memorySize`. Also check for memory leaks in game code — use the browser Memory tab to profile.

**Build loads correctly on localhost but shows errors in production**
Almost always a Cross-Origin Resource Sharing (CORS) issue. The CDN or web server must serve Unity's build files with correct headers. Check the browser console for specific CORS errors.

**"Unable to parse Build/MyGame.wasm.br"**
The web server is not setting `Content-Encoding: br`. Enable `decompressionFallback: true` or configure the server to set the header.

**Loading bar stalls at a specific percentage**
A specific asset or scene is failing to load. Check the browser console for detailed errors. Enable `dataCaching: false` and hard-refresh to rule out a stale cache.

**"SharedArrayBuffer is not defined"**
Unity's multithreading feature requires `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers. Set these on your web server or disable multithreading in Unity Player Settings.
