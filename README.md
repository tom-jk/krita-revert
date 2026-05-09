### File Revert plugin for Krita
Add a Revert action to the File Menu. Closes and reopens the document with the same views.

_feedback welcome._

#### Installation

##### Requirements
Compatible: Krita 5.3

Not tested: Krita 5.2 and earlier

Not compatible: Krita 6

Tested on Linux, but expected to work on Windows and Mac.

##### Instructions
Install in Krita following [these instructions](https://docs.krita.org/en/user_manual/python_scripting/install_custom_python_plugin.html). The revert action will be added to the File menu, and can also be added to toolbars with Settings → Configure Toolbars.

#### Limitations:
- properties like wraparound will look correct but might need toggling to actually function correctly.
- doesn't restore a view's fit view/width/height zoom setting, only the zoom value.
- for reasons, the reverted document is closed after the new one is open, so both briefly occupy memory.
- the views will move/flicker during revert.

#### Credits
Revert icon from KDE Breeze theme.

#### History
- [v1.0.1](https://github.com/tom-jk/krita-revert/releases/tag/v1.0.1) (Latest)
- v1.0.0
