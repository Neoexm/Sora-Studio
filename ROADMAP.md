# Sora Studio - Development Roadmap

## Phase 1: Core Data & Persistence ✅
- [x] Create `sora_core/models.py` with dataclasses (Project, Shot, Template, Settings, Profile)
- [x] Project file format (.sorastudio) with JSON serialization
- [x] Settings persistence (config.json)
- [x] Save/Load project functionality
- [x] Recent projects menu
- [x] Autosave mechanism
- [x] State restore (remember last prompt/model/size on startup)

## Phase 2: Queue System ✅
- [x] Create `sora_core/queue.py` with QueueManager
- [x] Queue panel UI (table/list with status)
- [x] Batch shots with per-shot params
- [x] Parallel job limit configuration
- [x] Reorder queue items
- [x] Cancel individual jobs
- [x] Persist queue state for resume across restarts
- [x] Profile-aware rate limiting

## Phase 3: Templates & Prompt Management ✅
- [x] Template data model
- [x] Templates panel UI
- [x] Create/edit/delete templates
- [x] Search and filter templates
- [x] Tags system
- [x] Pin/star favorites
- [x] Prompt history
- [x] Apply template to current shot

## Phase 4: CSV & Variable Expansion
- [ ] `{placeholder}` syntax in prompts
- [ ] CSV import wizard
- [ ] Column mapping UI
- [ ] Preview first 5 generated shots
- [ ] Auto-generate queue from CSV
- [ ] Variable validation

## Phase 5: Worker & Threading Improvements
- [ ] Visible Cancel button wired to Worker.cancel()
- [ ] Safe thread shutdown
- [ ] closeEvent cancels and joins threads
- [ ] Progress UX with ETA
- [ ] Last status text display
- [ ] Recent request IDs (copyable)
- [ ] Resume robustness with job cache

## Phase 6: Dynamic Capabilities
- [ ] Create `sora_core/capabilities.py`
- [ ] Query API for available models
- [ ] Fetch supported sizes/durations dynamically
- [ ] Cache capabilities (24h TTL)
- [ ] Update UI choices based on capabilities
- [ ] Disable invalid UI combos
- [ ] Verify against official OpenAI docs

## Phase 7: Advanced Safety & Moderation
- [ ] Show moderation explanation on blocks
- [ ] Parse flagged categories
- [ ] Suggest prompt rewrites
- [ ] "Rewrite & resend" button
- [ ] Safety settings in config

## Phase 8: Storyboard & Video Editing
- [ ] Storyboard editor UI
- [ ] Clip list management
- [ ] In/out point sliders
- [ ] Crossfade duration controls
- [ ] Title card support
- [ ] Export combined MP4 (ffmpeg integration)
- [ ] Preview stitched result

## Phase 9: Media Player
- [ ] QMediaPlayer + QVideoWidget integration
- [ ] Playback controls (play/pause/scrub)
- [ ] Frame-grab to PNG
- [ ] Contact sheet thumbnail generator
- [ ] Keyboard shortcuts (space, arrows)

## Phase 10: Post-Processing Hooks
- [ ] Post-processing command configuration
- [ ] Run external commands after download
- [ ] Capture command output
- [ ] ffmpeg filter presets
- [ ] Error handling for failed commands

## Phase 11: Notifications
- [ ] System tray integration
- [ ] Toast notifications on complete
- [ ] "Open folder" action
- [ ] "Re-run" action
- [ ] Notification preferences

## Phase 12: Multi-Profile Keys
- [ ] Profile data model
- [ ] Profile switcher UI
- [ ] Multiple API keys/orgs management
- [ ] Per-profile rate-limit tracking
- [ ] Per-profile backoff strategy

## Phase 13: Job Export & Metadata
- [ ] Sidecar JSON generation
- [ ] Save request params with video
- [ ] Save response metadata
- [ ] Filename sanitization with prompt slug
- [ ] Timestamp in filenames

## Phase 14: CLI Mode
- [ ] Create `sora_cli/__main__.py`
- [ ] Headless batch processing
- [ ] Process .sorastudio files
- [ ] Process template+CSV combos
- [ ] Single shot mode
- [ ] Non-zero exit on failure
- [ ] Progress output to stdout

## Phase 15: Drag & Drop / Paste
- [ ] Drag-and-drop for reference images
- [ ] Paste image from clipboard
- [ ] Reference image preview
- [ ] Auto-resize/crop/letterbox
- [ ] Show source vs target dimensions

## Phase 16: Localization & i18n
- [ ] i18n framework setup (QTranslator)
- [ ] Extract all UI strings
- [ ] Create translation files (.ts/.qm)
- [ ] Language selector
- [ ] Initial translations (en, es, fr, de, ja)

## Phase 17: Accessibility
- [ ] High-contrast mode
- [ ] Complete keyboard navigation
- [ ] Focus rings everywhere
- [ ] Screen reader labels
- [ ] Keyboard shortcut reference (Help menu)

## Phase 18: Auto-Update
- [ ] Create `sora_core/updates.py`
- [ ] Check GitHub Releases
- [ ] Version comparison
- [ ] Download updater per platform
- [ ] Hash verification
- [ ] Update prompt UI
- [ ] Install mechanism

## Phase 19: Settings Dialog
- [ ] Settings dialog UI (tabbed)
- [ ] General tab (poll interval, max wait, output dir)
- [ ] Queue tab (parallelism, retry settings)
- [ ] Profiles tab (manage keys)
- [ ] Post-processing tab (commands)
- [ ] Appearance tab (theme, font size)
- [ ] Advanced tab (disk threshold, logging)
- [ ] Apply/Cancel/OK buttons

## Phase 20: Diagnostics & Monitoring
- [ ] Latency test to API
- [ ] API status check
- [ ] Disk space readout
- [ ] Log bundle export (zip)
- [ ] Rate-limit headers display
- [ ] Cooldown countdown UI
- [ ] Diagnostics dialog

## Phase 21: Theming
- [ ] Light theme
- [ ] Dark theme
- [ ] System theme detection
- [ ] Proper color palettes
- [ ] Font size scaling (90-130%)
- [ ] Live theme switching
- [ ] Theme persistence

## Phase 22: Error Handling Improvements
- [ ] Unified error panel
- [ ] Copyable error details
- [ ] "Include in issue" button
- [ ] Parse 400/429 errors per docs
- [ ] Retry suggestions
- [ ] Exponential backoff with jitter

## Phase 23: UI Polish & Validation
- [ ] Remove duplicate widget construction in __init__
- [ ] Centralize UI creation in _setup_ui()
- [ ] Input validation (block empty fields)
- [ ] Inline validation messages
- [ ] Required field indicators
- [ ] Disable Generate when invalid

## Phase 24: Logs Improvements
- [ ] Log level filter
- [ ] Search in logs
- [ ] Save logs to file
- [ ] "Open logs folder" button
- [ ] Clear logs (Ctrl+L)
- [ ] Copy selected logs

## Phase 25: Response Viewer Enhancement
- [ ] Syntax highlighting for JSON
- [ ] Pretty-print formatting
- [ ] Copy JSON button
- [ ] Expand/collapse sections
- [ ] Dark/light theme support

## Phase 26: Keyboard Shortcuts
- [ ] Ctrl+Enter: Generate
- [ ] Esc: Cancel
- [ ] Ctrl+L: Clear log
- [ ] Ctrl+J: Copy Job ID
- [ ] Ctrl+S: Save project
- [ ] Ctrl+O: Open project
- [ ] Ctrl+N: New project
- [ ] Ctrl+,: Settings
- [ ] F1: Help

## Phase 27: Reference Image Handling
- [ ] Image preview widget
- [ ] Auto-resize before upload
- [ ] Crop/letterbox options
- [ ] Show dimensions comparison
- [ ] Format conversion if needed
- [ ] Size warning if too large

## Phase 28: Disk Space Management
- [ ] Check free space before generate
- [ ] Display free space in UI
- [ ] Configurable threshold
- [ ] Warning dialog on low space
- [ ] Estimate video size

## Phase 29: Cross-Platform Packaging ✅
- [x] Windows .exe (PyInstaller)
- [x] macOS .app/.dmg (py2app + create-dmg)
- [x] Linux AppImage
- [x] Portable mode toggle
- [x] CI/CD workflow (GitHub Actions)
- [x] Multi-OS build artifacts
- [ ] Release upload automation (manual artifact downloads for now)
- [x] ImageMagick integration for icon conversion
- [x] Proper .desktop file creation
- [x] Icon placement for AppImage

## Phase 30: Code Quality & Testing
- [ ] Configure ruff + black in pyproject.toml
- [ ] Type hints everywhere
- [ ] mypy --strict compliance
- [ ] Unit tests for templating
- [ ] Unit tests for CSV expansion
- [ ] Unit tests for filename logic
- [ ] Unit tests for queue scheduling
- [ ] Integration tests for worker
- [ ] CI gates (lint, type check, test)

## Phase 31: Documentation
- [ ] Update README with all features
- [ ] User guide
- [ ] API documentation
- [ ] Contributing guide
- [ ] Changelog
- [ ] License
- [ ] Screenshots

---

## What's Working Now
- Base application with video generation
- Compact preview with expandable dialog
- Adjustable/collapsible output panel
- Layout validation
- Basic error handling
- API key management
- **COMPLETE cross-platform packaging with CI/CD automation**
- **GitHub Actions workflow building Windows, macOS, and Linux binaries**
- **Automatic artifact uploads for all three platforms**

## Recently Completed
- Phase 1: Complete data persistence layer with project files
- Phase 2: Full queue system with parallel job management
- Phase 3: Templates & Prompt Management system
  - Template CRUD operations with full parameter support
  - Search and filter by name, prompt, tags
  - Pin/star favorite templates
  - Prompt history tracking (last 20 prompts)
  - Quick apply template to current shot
- Phase 29: Cross-platform packaging infrastructure
  - Windows executable with PyInstaller
  - macOS DMG with custom volume and app bundle
  - Linux AppImage with proper desktop integration
  - GitHub Actions CI/CD pipeline
  - Automated builds on push to main branch

## Priority
Start with Phase 1 (persistence layer) since most other features depend on it. Phase 6 (dynamic capabilities) would be good to tackle early too - removes hardcoded stuff and makes everything more flexible. Queue system (Phase 2) and templates (Phase 3) are high-value features that should come after the foundation is solid.

The rest can be added based on what's actually useful in practice.
