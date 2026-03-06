# Keyboard Shortcuts Update

## Overview
All keyboard shortcuts have been updated to require modifier keys (Ctrl/Alt/Shift) following standard keyboard norms and avoiding system shortcut conflicts. Shortcuts have been re-enabled.

## Changes Made

### 1. Enabled Shortcuts
- Set `DISABLE_SHORTCUTS = False` in:
  - [src/phage_annotator/ui_qt/actions/keyboard_events.py](src/phage_annotator/ui_qt/actions/keyboard_events.py#L15)
  - [src/phage_annotator/ui_qt/utils/ui_setup.py](src/phage_annotator/ui_qt/utils/ui_setup.py#L29)

### 2. Updated Shortcut Mappings

All shortcuts now use modifier keys to prevent conflicts with text input and system shortcuts:

| Action | Old Shortcut | New Shortcut | Reasoning |
|--------|-------------|--------------|-----------|
| Play/Pause | Space | Ctrl+Space | Prevent conflict with typing space |
| Navigate Time (Prev) | Left | Alt+Left | Standard Alt+Arrow for app navigation |
| Navigate Time (Next) | Right | Alt+Right | Standard Alt+Arrow for app navigation |
| Navigate Z (Up) | Up | Alt+Up | Standard Alt+Arrow for app navigation |
| Navigate Z (Down) | Down | Alt+Down | Standard Alt+Arrow for app navigation |
| Accept Suggestion | A | Ctrl+A | Prevent conflict with typing letter 'A' |
| Accept Current | Alt+A / Enter | Ctrl+Shift+A | Consistent modifier pattern |
| Reject Suggestion | R | Ctrl+Shift+R | Prevent conflict with typing letter 'R' |
| Next Suggestion | N | Ctrl+N | Prevent conflict with typing letter 'N' |
| Previous Suggestion | P | Ctrl+P | Prevent conflict with typing letter 'P' |
| Review Context | Ctrl+Alt+R | Ctrl+Alt+V | Avoid conflict with reset view |
| Reset View | Ctrl+R | Ctrl+0 | Standard zoom reset shortcut |
| Clear ROI | Shift+R | Ctrl+Shift+Delete | More explicit modifier combination |
| Delete Selected | Delete / Backspace | Delete | Simplified to standard delete key |
| Cycle Colormap | C | Ctrl+Shift+C | Prevent conflict with typing letter 'C' |
| Quick Save | S | Ctrl+S | Standard save shortcut |
| Label Previous | [ | Ctrl+[ | Added modifier for consistency |
| Label Next | ] | Ctrl+] | Added modifier for consistency |
| Focus Canvas | F | Alt+F | Prevent conflict with typing letter 'F' |
| Fast Label Select | 1-9 | Ctrl+1-9 | Prevent conflict with typing numbers |

### 3. Deprecated Matplotlib Direct Key Bindings

Removed single-key Matplotlib shortcuts to prevent accidental activation:
- Removed "r" → reset_view
- Removed "c" → cycle_colormap  
- Removed "s" → quick_save

These now use Qt key events with proper modifiers:
- Ctrl+0 for reset view
- Ctrl+Shift+C for cycle colormap
- Ctrl+S for quick save

### 4. Code Changes

#### [keyboard_registry.py](src/phage_annotator/ui_qt/keyboard_registry.py)
- Updated `SHORTCUTS` tuple with new modifier-based shortcuts
- Updated `qt_key_bindings()` function to map Qt keys with proper modifiers
- Cleared `matplotlib_key_bindings()` dict (deprecated single-key shortcuts)

#### [keyboard_events.py](src/phage_annotator/ui_qt/actions/keyboard_events.py)
- Changed fast label selection from bare `1-9` to `Ctrl+1-9`
- Deprecated `_on_key()` Matplotlib handler (now empty)
- Added `cycle_colormap` handler to Qt `keyPressEvent()`
- Set `DISABLE_SHORTCUTS = False`

#### [ui_setup.py](src/phage_annotator/ui_qt/utils/ui_setup.py)
- Set `DISABLE_SHORTCUTS = False`

## Standard Keyboard Norms Followed

1. **Ctrl for Commands**: Primary actions use Ctrl (Ctrl+S for save, Ctrl+A for accept, Ctrl+N for next)
2. **Alt for Alternatives**: App-specific navigation uses Alt (Alt+Arrows, Alt+F for focus)
3. **Shift for Variants**: Shift modifies related actions (Ctrl+Shift+A for accept current, Ctrl+Shift+R for reject)
4. **No System Conflicts**: Avoided common OS shortcuts (Ctrl+C/V/X for clipboard, Ctrl+Q/W/T for window management)
5. **Consistent Patterns**: Related actions use similar modifier patterns

## System Shortcuts Avoided

- Ctrl+C/V/X (clipboard operations)
- Ctrl+Q/W (quit/close window)
- Ctrl+T (new tab)
- Ctrl+N (new window - used for Next Suggestion which is app-specific)
- Alt+F4 (close window)
- Ctrl+Alt+Del (system)

## Testing Recommendations

1. **Text Input**: Verify that typing letters A, R, N, P, F, C, S no longer triggers actions
2. **Number Input**: Verify that typing numbers 1-9 no longer changes labels
3. **Navigation**: Test Alt+Arrow keys for time/Z navigation
4. **Suggestions**: Test Ctrl+A (accept), Ctrl+Shift+R (reject), Ctrl+N/P (next/prev)
5. **Label Selection**: Test Ctrl+1 through Ctrl+9 for fast label switching
6. **View Control**: Test Ctrl+0 (reset), Ctrl+Shift+C (colormap), Ctrl+S (save)
7. **System Shortcuts**: Verify Ctrl+C/V still work for copy/paste in text fields

## Migration Notes

Users will need to update muscle memory for changed shortcuts. Key changes:
- Space → Ctrl+Space for play/pause
- Arrow keys → Alt+Arrow keys for navigation
- Single letters → Ctrl/Alt+Letter for actions
- Numbers → Ctrl+Number for label selection

Consider displaying a "Shortcuts Updated" notification on first launch after this change.
