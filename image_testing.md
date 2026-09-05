# Image Integration Testing Playbook

## Image Handling Rules
- Always use base64-encoded images for all tests and requests.
- Accepted formats: JPEG, PNG, WEBP only.
- Do not use SVG, BMP, HEIC, or other formats.
- Do not upload blank, solid-color, or uniform-variance images.
- Every image must contain real visual features — objects, edges, textures, or shadows.
- If not PNG/JPEG/WEBP, transcode to PNG or JPEG before upload; re-detect MIME after transforms.
- If animated (GIF/APNG/animated WEBP), extract the first frame only.
- Resize large images to reasonable bounds (avoid oversized payloads).
