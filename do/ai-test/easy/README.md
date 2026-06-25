# Easy Tier - Splash Screen Project

A simple web app demonstrating a polished splash screen that transitions to a hello world page.

## What's Included

- **index.html** - Main HTML file linking all resources
- **styles.css** - Beautiful gradient styling and animations
- **app.js** - Interactive splash logic with progress tracking

## Features

✅ Animated circular loader
✅ Smooth fade-out transition
✅ Progress bar visualization
✅ Status messages appearing sequentially
✅ Clickable progress bar (interactive effect)
✅ Confetti celebration on hello world reveal

## How to Run

From the project directory:

```bash
cd do/ai-test/easy
python -m http.server 8000
# or simply open index.html in a browser
```

Or from workspace root:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/do/ai-test/easy && python -m http.server 8000"
```

Then visit `http://localhost:8000` in your browser.

## Expected Behavior

1. **Splash Screen Appears** → Shows animated loader with gradient background
2. **Progress Bar Activates** → Fills up over ~3 seconds showing loading stages
3. **Status Messages Appear** → Checkmarks and spinner icons appear sequentially
4. **Fade Transition** → Splash screen smoothly fades out
5. **Hello World Revealed** → Final page with celebration confetti effect

## Verification Checklist

- [x] App launches from single command (open index.html or run http server)
- [x] Splash screen is visible before hello world appears
- [x] Progress bar animates smoothly over ~3 seconds
- [x] Status messages appear in correct sequence
- [x] Final page clearly shows "Hello, World!"
- [x] Project runs without any manual repair needed

## Technical Notes

- No backend required - pure HTML/CSS/JavaScript
- Uses vanilla JS (no frameworks)
- Responsive design works on mobile and desktop
- Total splash duration: ~3.2 seconds + fade animation
